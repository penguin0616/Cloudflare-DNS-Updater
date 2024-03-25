#!python
import requests
import json
import argparse


session = None
dnsRecordCache = {}



def createSession(apiKey: str):
	global session

	# Create session
	session = requests.session()
	session.headers["Authorization"] = f"Bearer {apiKey}"
	session.headers["Content-Type"] = "application/json"
	# session.verify = False


def getIPAddress():
	# Get our IP address
	res = session.get("http://api.ipify.org")

	if res.status_code != 200:
		print(res.text)
		raise Exception(f"Ipify returned status code {res.status_code}")

	ip = res.text
	return ip



# Cloudflare stuff
def getZones():
	"""
	Gets a list of zones for the client.

	https://developers.cloudflare.com/api/operations/zones-get
	[Zone -> List Zones]

	:return:
	"""
	
	res = session.get("https://api.cloudflare.com/client/v4/zones")
	if res.status_code != 200:
		print(res.text)
		raise Exception(f"Cloudflare returned error getting zones; status code {res.status_code}")

	zoneList = res.json()["result"]
	return zoneList


def getDNSRecords(zoneId: str, ignoreCache: bool = False):
	"""
	Obtains a list of DNS records for a zone.

	Documentation:
	https://developers.cloudflare.com/api/operations/dns-records-for-a-zone-list-dns-records
	[DNS Records for a Zone -> List DNS Records]
	
	:param zone_id: The ID for the zone.
	:return:
	"""

	global dnsRecordCache

	# If the records are cached, just use that.
	if not ignoreCache and (zoneId in dnsRecordCache):
		return dnsRecordCache[zoneId]


	res = session.get(f"https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records")
	if res.status_code != 200:
		print(res.text)
		raise Exception(f"Cloudflare returned error getting DNS records for a zone; status code {res.status_code}")

	dnsRecords = res.json()["result"]

	dnsRecordCache[zoneId] = dnsRecords

	return dnsRecords



def updateDNSRecord(zoneId: str, recordId: str, newIP: str):
	"""
	Updates a DNS record to use the specified IP address.
	
	:param zoneId:
	:param recordName:
	:param newIP:
	"""

	res = session.patch(f"https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records/{recordId}", json.dumps({
		"content": newIP
	}))
	if res.status_code != 200:
		print(res.text)
		raise Exception(f"Cloudflare returned error updating a DNS record for a zone; status code {res.status_code}")
	
	# All good?
	


def findAndUpdateDNSRecord(zoneId: str, recordName: str, newIP: str):
	"""
	Finds the DNS record that matches the recordName, and updates it to use the specified IP address.
	
	:param zoneId:
	:param recordName:
	:param newIP:
	"""

	dnsRecords = getDNSRecords(zoneId)

	for record in dnsRecords:
		if record["name"] == recordName:
			
			if record["content"] == newIP:
				print("DNS record '{}' ({}) is already up to date with [{}]".format(recordName, record["id"], record["content"]))
				break

			updateDNSRecord(zoneId, record["id"], newIP)
			print("Updated DNS record '{}' ({}) from [{}] to [{}]".format(recordName, record["id"], record["content"], newIP))
			break

	# print(f"Updated DNS record {recordId}")


def main(apiKey: str, recordsToUpdate: list[str]):
	createSession(apiKey)
	ip = getIPAddress()
	print(f"Current IP Address: {ip}")

	zones = getZones()
	
	for record in recordsToUpdate:
		# Get the zone that belongs to the record.
		zone = [ x for x in zones if record.endswith(x["name"]) ]
		
		if len(zone) == 0:
			print(f"Unable to find zone for record '{record}'")
			continue
		
		zone = zone[0]

		findAndUpdateDNSRecord(zone["id"], record, ip)

		



# Init
parser = argparse.ArgumentParser(
	prog="update_cloudflare_records",
	description="Updates Cloudflare DNS records with your current IP address.\nMade because I couldn't get DDclient to work.",
	epilog="Example use: path-to-script.py --api-key <api-key> -r domain.tld -r xyz.domain.tld"
)

parser.add_argument("--api-key", required=True, help="The API key to use. Doesn't support the Global API key.")
parser.add_argument("-r", "--record", action="append", help="Record to update. Ex: domain.tld OR xyz.domain.tld. Can be specified multiple times.")


if __name__ == "__main__":
	args = parser.parse_args()

	if args.record is None:
		print("Error: No records were specified.")
		exit(1)

	main(args.api_key, args.record)