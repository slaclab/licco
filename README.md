Line configuration management

aka. Machine Configuration Database

see: https://confluence.slac.stanford.edu/display/PCDS/Validated+Machine+Configuration+Database+System 


### Install Steps

- Create the conda environment from the base directory
    - `conda env create -f environment.yml`
- Activate the conda environment by name(see .yml file for correct name)
    - `conda activate mcd_0_0_1`
- Install flask_authnz submodule
    - Update and activate submodule
- Install javascript packages from within react folder
    - `cd react`
    - `npm install` OR copy over a node_modules folder installed on a machine with the same build requirements
- Start front end REACT development server 
    - `npm run dev`
- Run backend in debug mode with gunicorn server in another terminal/session
    - `LOG_LEVEL=DEBUG MONGODB_URL=127.0.0.1 python3 -m gunicorn start:app`


## Configuration

### Credentials

In order for notification module to work, you have to create a `credentials.ini`
file in the main directory, e.g.:

```ini
# example credentials.ini file
[email]
service_url = https://localhost:3000
url = smtp.example.com
port = 587
email_auth = False
user = user.name@example.com
password = password
admin_email = admin@admin.com
username_to_email_service = http://www.example.com/ws/
```
