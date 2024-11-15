Line configuration management

aka. Machine Configuration Database

see: https://confluence.slac.stanford.edu/display/PCDS/Validated+Machine+Configuration+Database+System 


## Credentials

In order for notification module to work, you have to create a `credentials.ini`
file in the main directory, e.g.:

```ini
# example credentials.ini file
[email]
url = smtp.example.com
port = 587
user = user.name@example.com
password = password
username_to_email_service = http://www.example.com/ws/
```