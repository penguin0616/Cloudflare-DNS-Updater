# Hi

This Python script is used to update your DNS records on Cloudflare with your current public IPv4.  
I made it because I couldn't get DDclient to work.

# Usage

```python
main.py --api-key <YOUR_API_KEY> -r domain.tld -r xyz.domain.tld
```

The script will automatically look for the correct zones based on the ``domain.tld`` part of the records you specify.  
It will not redundantly update records.  