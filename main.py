#!python
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import requests
from cloudflare import Cloudflare
import cloudflare.types.zones
import cloudflare.types.dns

################################################################################

API_TOKEN_ENVIRONMENT_VARIABLE = "CLOUDFLARE_DNS_UPDATER_API_TOKEN"

client: Cloudflare = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# https://docs.python.org/3/library/logging.html#logrecord-attributes

# https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler
file_handler = RotatingFileHandler(os.path.join(os.path.split(__file__)[0], "log.log"), mode="a", maxBytes=1000000, backupCount=3)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(fmt="[%(asctime)s] %(levelname)-8s : %(message)s", datefmt="%m/%d/%Y %H:%M:%S"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(fmt="[%(levelname)s] %(message)s", datefmt="%m/%d/%Y %H:%M:%S"))
logger.addHandler(console_handler)

################################################################################

# This is pretty bad, but we're doing a second round of imports.

try:
	import dotenv
	found = dotenv.load_dotenv()
	if found:
		logger.debug("dotenv successfully found environment variables.")
	else:
		logger.debug("dotenv did not find any environment variables.")
except ImportError:
	logger.debug("Did not find python-dotenv; ignoring .env files.")

try:
	YAML = None
	from ruamel.yaml import YAML
	logger.debug("Found ruamel.yaml")
except ImportError:
	logger.debug("Did not find ruamel.yaml; ignoring .yaml files")


################################################################################

def get_ip_address() -> str:
	"""
	Queries an external service to get our external IP address.

	:return: IPv4 address of client.
	"""
	# Get our IP address
	res = requests.get("http://api.ipify.org")

	if res.status_code != 200:
		raise Exception(f"Ipify returned error ({res.status_code}) while querying IP", res.text)

	ip = res.text
	return ip


def load_config_file(filepath: str) -> dict:
	filename, ext = os.path.splitext(filepath)

	filepath = os.path.abspath(filepath)

	data = None

	# Load the data based on filetype.
	if ext == ".yaml": 
		if not YAML:
			logger.error("Cannot load .yaml files without installing ruamel.yaml; See https://pypi.org/project/ruamel.yaml/")
			exit(1)
		
		yaml = YAML(typ="safe")
		with open(filepath) as f:
			data = yaml.load(f)
	
	elif ext == ".json":
		with open(filepath) as f:
			data = json.load(f)

	else:
		logger.error(f"Unrecognized file extension for \"{filepath}\"")
		exit(1)

	# Make sure it is a dictionary.
	data_type = type(data)
	if data_type != dict:
		logger.error(f"Config file expected to be a dictionary, not a [{data_type}]")
		exit(1)

	# Make sure that the records field is a list, provided it exists.
	if "records" in data:
		records_type = type(data["records"])
		if records_type != list:
			logger.error(f"Expected records field \"records\" to be a list, not [{records_type}]")

	return data


def main(args: argparse.Namespace):
	# Load configuration file
	config = {}
	if args.config:
		config = load_config_file(args.config)

	# Get the API token
	api_token = args.api_token
	if not api_token:
		# Okay, check if it's in the config file.
		api_token = config.get("api_token")

		if not api_token:
			# Perhaps it's in the environment?
			api_token = os.getenv(API_TOKEN_ENVIRONMENT_VARIABLE)
			if not api_token:
				logger.error("Error: No API token was provided. If you're doing it through an env file, did you forget to install python-dotenv?")
				exit(1)

	# Get the records that need to be updated.
	records_to_update = args.record
	#logger.debug(f"Records from command line: {records}")

	if "records" in config:
		records_to_update += config["records"]
	else:
		logger.debug("Configuration file did not specify any records.")

	if len(records_to_update) == 0:
		logger.error("There were no records specified, exiting.")
		exit(0)

	logger.info(f"Records: {records_to_update}")

	# Create our cloudflare client and validate it
	client = Cloudflare(api_token=api_token)
	client.user.tokens.verify()

	# Get current IP address
	ip = get_ip_address()
	logger.info(f"Current IP Address: {ip}")

	# Get all of the zones visible to our token
	zones: list[cloudflare.types.zones.Zone] = []

	for page in client.zones.list().iter_pages():
		zones += page.result
	

	# Keep track of the known DNS records so if we hit one we already know, 
	# we can just reuse our cache instead of making another request.
	known_dns_records: dict[str, list[cloudflare.types.dns.Record, cloudflare.types.zones.Zone]] = {}


	gathered_exceptions = []
	num_changed = 0
	num_errored = 0

	# Start matching records against zones
	for record_name in records_to_update:
		dns_record = None
		zone = None

		# Check if we already have the DNS record for this.
		if record_name in known_dns_records:
			dns_record, zone = known_dns_records[record_name]
		else:
			record_chunks = record_name.split(".")
			root_domain = ".".join(record_chunks[-2:])

			# Get the zone that belongs to the record.
			# logger.debug("%s; %s", record_name, root_domain)
			zone = [ z for z in zones if z.name == root_domain ]
			
			if len(zone) == 0:
				logger.warning(f"Unable to find zone for record \"{record_name}\"")
				num_errored += 1
				continue
		
			# We have the zone, now get the DNS records associated with the zone.
			zone = zone[0]
			for page in client.dns.records.list(zone_id=zone.id).iter_pages():
				for r in page.result:
					if r.type == "A":
						known_dns_records[r.name] = [r, zone]
						if r.name == record_name:
							dns_record = r
							break

		# Make sure we got a record to update.
		if dns_record is None:
			logger.warning(f"Unable to find DNS record for \"{record_name}\"")
			num_errored += 1
			continue
		
		if dns_record.content == ip:
			logger.info(f"Record \"{record_name}\" is already up to date with address [{dns_record.content}]!")
			continue

		if args.dry:
			logger.info(f"Would have updated record \"{record_name}\" from [{dns_record.content}] to [{ip}]")
			num_changed += 1
		else:
			#logger.info(f"Attempting to update the DNS record for {record_name}")
			try:
				# The naming on this is a little messed up. 
				# I thought it was .update, but .update is actually OVERWRITE: https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/update/
				# UPDATE is actually .edit: https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/edit/
				# I'm not sure why the endpoint only needs dns record and zone id, but this also needs name and type.
				client.dns.records.edit(dns_record_id=dns_record.id, zone_id=zone.id, content=ip, name=dns_record.name, type=dns_record.type)
				logger.info(f"Updated record \"{record_name}\" from [{dns_record.content}] to [{ip}]")
				num_changed += 1
			except Exception as err:
				logger.error(f"Encountered an error updating the DNS record for \"{record_name}\"")
				logger.exception(err)
				gathered_exceptions.append(err)
	

	num_errored += len(gathered_exceptions)
	num_records = len(records_to_update)
	logger.info(f"Out of [{num_records}] records: [{num_changed}] were updated, [{num_errored}] had a problem, [{num_records-num_changed-num_errored}] had nothing happen.")

	if len(gathered_exceptions) > 0:
		raise ExceptionGroup("The following exceptions occured during execution", gathered_exceptions)


		
################################################################################


# Init
parser = argparse.ArgumentParser(
	prog="update_cloudflare_records",
	description="Updates Cloudflare DNS records with your current IP address.\nMade because I couldn't get DDclient to work.",
	epilog="Example use: main.py --api-token <api_token> -r domain.tld -r xyz.domain.tld"
)

parser.add_argument("--api-token", help="The API token to use. If not provided, will try to load the environment variable \"{}\". Doesn't support the Global API key.".format(API_TOKEN_ENVIRONMENT_VARIABLE))
parser.add_argument("--dry", action="store_true", help="Performs a dry run, not actually updating the records.")
parser.add_argument("-r", "--record", action="append", default=[], help="Record to update. Ex: domain.tld OR xyz.domain.tld. Can be specified multiple times.")
parser.add_argument("-c", "--config", type=str, help="A YAML or JSON file to load configuration from.")


if __name__ == "__main__":
	args = parser.parse_args()

	try:
		main(args)
	except Exception as err:
		logger.exception(err)