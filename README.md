# Hi

This Python script is used to update your DNS records on Cloudflare with your current public IPv4.  
I made it because I couldn't get DDclient to work.

# Requirements
Requests is all you need. As long as the version isn't super old, it'll probably work.

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

# Usage

``<YOUR_API_KEY>`` is the same as ``<TOKEN>`` in the above example.

```python
main.py --api-key <YOUR_API_KEY> -r domain.tld -r xyz.domain.tld
```

The script will automatically look for the correct zones based on the ``domain.tld`` part of the records you specify.  
It will not redundantly update records.  


# Setting it up as a systemd service to run every so often.
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
ExecStart=python3 /home/<user>/Cloudflare-DNS-Updater/main.py --api-key <api-key> -r domain.tld -r xyz.tld -r abc.domain.tld

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflare-dns-updater.service
```