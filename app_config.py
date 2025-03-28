import configparser
import os
from dataclasses import dataclass, asdict, field


@dataclass
class EmailConfig:
    # url that determines the base url path of the licco service, so that the sent emails
    # construct correct urls to projects
    licco_service_url = ""

    # if True: emails will be sent via smtp endpoint using the url/port/auth below
    # if False: emails will be displayed in the console only
    send_emails: bool = False

    # smtp endpoint
    url: str = ""
    port: int = -1

    # auth
    email_auth: bool = False
    user: str = ""
    password: str = ""

    # admin email that will appear in notifications
    admin_email: str = ""

    # service which licco is using to query user's email addresses
    username_to_email_service: str = ""

    def __str__(self):
        fields = {}
        for field, value in asdict(self).items():
            if field == 'password':
                fields[field] = "****"
            else:
                fields[field] = value
        return "\n".join(f"{field}: {value}" for field, value in fields.items())


def default_email_config():
    return EmailConfig()


@dataclass
class AppConfig:
    """Class for storing application wide configuration"""

    # Flask app config
    app_send_file_max_age_default: int = 300
    app_secret_key: str = "A secret key for licco"
    app_debug: bool = False
    app_log_level: str = "INFO"

    # database config
    mongo_url: str = ""
    mongo_connection_timeout: int = 5000

    # email config
    email_config: EmailConfig = field(default_factory=default_email_config)

    def populate_from_parsed_config(self, c: configparser.ConfigParser):
        self.app_send_file_max_age_default = c.get("app", "send_file_max_age_default", fallback=300)
        self.app_secret_key = c.get("app", "secret_key", fallback="A secret key for licco")
        self.app_debug = c.get("app", "debug", fallback=False)
        self.app_log_level = c.get("app", "log_level", fallback="INFO")

        mongo_backup = os.environ.get("MONGODB_URL", "")
        self.mongo_url = c.get("db", "mongo_url", fallback=mongo_backup)
        self.mongo_connection_timeout = c.get("db", "mongo_connection_timeout", fallback=5000)

        # load email config
        if "email" in c:
            self.email_config.licco_service_url = c.get("email", "licco_service_url")
            self.email_config.send_emails = c.getboolean("email", "send_emails", fallback=False)
            self.email_config.url = c.get("email", "url")
            self.email_config.port = c.get("email", "port")
            self.email_config.email_auth = c.getboolean("email", "email_auth", fallback=False)
            self.email_config.user = c.get("email", "user")
            self.email_config.password = c.get("email", "password", fallback="")
            self.email_config.admin_email = c.get("email", "admin_email")
            self.email_config.username_to_email_service = c.get("email", "username_to_email_service_url")
        else:
            # no email is present, that means we have to turn email sending off (we are in development mode)
            self.email_config.send_emails = False

    def __str__(self):
        fields = {}
        for field, value in asdict(self).items():
            if field == 'email_config':
                indented_fields = "\n"
                for line in str(self.email_config).splitlines(keepends=True):
                    indented_fields += "    " + line
                fields[field] = indented_fields
            else:
                fields[field] = value
        return "\n".join(f"{field}: {value}" for field, value in fields.items())


def load_config(config_path: str) -> AppConfig:
    if not config_path:
        print("Application config filepath was not provided: loading a default configuration")
        p = configparser.ConfigParser()
        p.read_string("")
        ac = AppConfig()
        ac.populate_from_parsed_config(p)
        return ac

    # path exists, check if it also exists on the hdd
    if not os.path.exists(config_path):
        raise Exception(f"App configuration path '{config_path}' does not exist")

    parser = configparser.ConfigParser()
    parser.read(config_path)
    ac = AppConfig()
    ac.populate_from_parsed_config(parser)
    return ac
