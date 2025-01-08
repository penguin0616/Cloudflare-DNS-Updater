# Hi

This Python script is used to update your DNS records on Cloudflare with your current public IPv4.  
I made it because I couldn't get DDclient to work.

# Requirements

[Requests](https://pypi.org/project/requests/) and [Cloudflare](https://github.com/cloudflare/cloudflare-python) is the minimum requirements.
If you want YAML (1.2) support, install [ruamel.yaml](https://pypi.org/project/ruamel.yaml/)  
If you want .env file support, install [python-dotenv](https://pypi.org/project/python-dotenv/)  

All of the above are recommended.

Tested on Python 3.12.5, but should be compatible to at least mid 3s?

# Cloudflare setup

1. Go to https://dash.cloudflare.com/profile/api-tokens and create an API token. 
2. Press "Use Template" for "Edit zone DNS".
3. Settings should look like this:
```
Zone		DNS								Edit
Include		All zones from an account 		<email>
```

You can verify the token by doing:
```bash
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type:application/json"
```

# Sample Usage

``<YOUR_API_TOKEN>`` is the same as ``<TOKEN>`` in the above example.

The script will automatically look for the correct zones based on the ``domain.tld`` part of the records you specify.  
It will not redundantly update records.  

## Config & .env files (HIGHLY RECOMMENDED)

I recommend creating a ``config.yaml`` (or ``config.json``) at the very least to put your DNS records in.  
As for the API token, you can either use a ``.env`` file or the token into your environment variables. You *also* could put it in the config files, but this is not recommended.  
The code checks for the presence of the ``CLOUDFLARE_DNS_UPDATER_API_KEY`` in the environment.  

See the sample files for reference.

## Command Line

Remove ``--dry`` to actually update the records.

### Manual

```python
main.py --api-token <YOUR_API_TOKEN> -r domain.tld -r xyz.domain.tld --dry
```

### Recommended
```python
main.py --config <PATH_TO_CONFIG_FILE> --dry
```

# Setting it up as a systemd service to run every so often.

The script will generate a log file in the directory that it is contained in, rotating up to 3 log files every megabyte.

```bash
sudo nano /etc/systemd/system/cloudflare-dns-updater.timer
```

```ini
[Unit]
Description=Triggers the updater.
Requires=cloudflare-dns-updater.service

[Timer]
OnBootSec=60
OnUnitActiveSec=6h

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflare-dns-updater.timer
```


## Service file

```bash
sudo nano /etc/systemd/system/cloudflare-dns-updater.service
```

```ini
[Unit]
Description=cloudflare-dns-updater
After=network.target
Wants=cloudflare-dns-updater.timer

[Service]
Type=oneshot
user=<user>
group=<group>
Environment="PYTHONPATH=/home/<user>/.local/lib/python3.10/site-packages"
ExecStart=python3 /home/<user>/Cloudflare-DNS-Updater/main.py --config /home/<user>/Cloudflare-DNS-Updater/config.yaml

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflare-dns-updater.service
```