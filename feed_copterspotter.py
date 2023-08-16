#!/usr/bin/env python3

"""
Upload rotorcraft positions to Helicopters of DC
"""

import json
import csv

# unused

# from datetime import timezone

import datetime
import logging
import argparse
import sys
import os
from time import sleep, ctime, time, strftime

import requests
import daemon


# used for getting MONGOPW and MONGOUSER
from dotenv import dotenv_values  # , set_key


# only need one of these
import pymongo

# from pymongo import MongoClient


## YYYYMMDD_HHMM_REV
VERSION = "20230323_1300_001"

# Bills

BILLS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv"

BILLS_TIMEOUT = 86400  # Standard is 1 day


# Mongo URL
MONGO_URL = (
    "https://us-central1.gcp.data.mongodb-api.com/app/feeder-puqvq/endpoint/feedadsb"
)

# curl -v -H "api-key:BigLongRandomStringOfLettersAndNumbers" \
#  -H "Content-Type: application/json" \-d '{"foo":"bar"}' \
#  https://us-central1.gcp.data.mongodb-api.com/app/feeder-puqvq/endpoint/feedadsb

# but filling in foo-bar with our entry structured like this:
# {"type":"Feature",
#   "properties":{"date":{"$numberDouble":"1678132376.867"},
#   "icao":"ac9f65",
#   "type":"MD52",
#   "call":"GARDN2",
#   "heading":{"$numberDouble":"163.3"},
#   "squawk":"5142",
#   "altitude_baro":{"$numberInt":"625"},
#   "altitude_geo":{"$numberInt":"675"},
#   "feeder":


formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# create formatter

logger = logging.getLogger(__name__)


# list of folders to check for dump1090 json files
# FR24: /run/dump1090-mutability
# ADSBEXchange location: /run/adsbexchange-feed
# Readsb location: /run/readsb
# anecdotally I heard some images have data in:  /run/dump1090/data/
# Flight Aware /run/dump1090-fa


AIRPLANES_FOLDERS = [
    "dump1090-fa",
    "dump1090-mutability",
    "adsbexchange-feed",
    "readsb",
    "dump1090",
    "adbsfi-feed",
]


# Trying to make this more user friendly

CONF_FOLDERS = [
    "~/.CopterFeeder",
    "~/CopterFeeder",
    "~",
    ".",
]

# Hard Coding User/Pw etc is bad umkay
# Should be pulling thse from env
#    FEEDER_ID = ""
#    AIRPLANES_FOLDER = "adsbexchange-feed"
#    # FR24: dump1090-mutability
#    # ADSBEXchange location: adsbexchange-feed
#    # Readsb location: readsb
#    MONGOUSER = ""
#    MONGOPW = ""


# Deprecated with "requests" pull to localhost:8080
# AIRPLANES_FOLDER = "dump1090-fa"
# FR24: dump1090-mutability
# ADSBEXchange location: adsbexchange-feed
# Readsb location: readsb


def mongo_client_insert(mydict):
    """
    Insert one entry into Mongo db
    """

    #   password = urllib.parse.quote_plus(MONGOPW)

    #   This needs to be wrapped in a try/except
    myclient = pymongo.MongoClient(
        "mongodb+srv://"
        + MONGOUSER
        + ":"
        + MONGOPW
        + "@helicoptersofdc.sq5oe.mongodb.net/?retryWrites=true&w=majority"
    )

    mydb = myclient["HelicoptersofDC"]
    mycol = mydb["ADSB"]

    #   This needs to be wrapped in a try/except
    ret_val = mycol.insert_one(mydict)

    return ret_val


def mongo_https_insert(mydict):
    """
    Insert into Mongo using HTTPS requests call
    """
    # url = "https://us-central1.gcp.data.mongodb-api.com/app/feeder-puqvq/endpoint/feedadsb"

    headers = {"api-key": MONGO_API_KEY, "Content-Type": "application/json"}

    response = requests.post(MONGO_URL, headers=headers, json=mydict, timeout=7.5)
    logger.info("Mongo Insert Status: %s", response.status_code)

    return response.status_code


def update_helidb():
    """Main"""

    logger.info("Updating Helidb at %s", datetime.datetime.now())

    try:
        #        with open("/run/" + AIRPLANES_FOLDER + "/aircraft.json") as json_file:
        #        data = json.load(json_file)
        #       planes = data["aircraft"]

        #       Use this if checking returns from the request
        #       req = requests.get('http://localhost:8080/data/aircraft.json')
        #       planes = req.json()["aircraft"]

        #       use this if assuming the request succeeds and spits out json

        data = None

        # The following if / else should probably be outside of this function as
        # it should only be done at startup time.

        if AIRCRAFT_URL:
            try:
                data = requests.get(AIRCRAFT_URL, timeout=5)
                if data.status_code == 200:
                    logger.debug("Found data at URL: %s", AIRCRAFT_URL)
                    dt_stamp = data.json()["now"]
                    logger.debug("Found TimeStamp %s", dt_stamp)
                    planes = data.json()["aircraft"]

            except requests.exceptions.RequestException as e:
                logger.error("Got ConnectionError trying to request URL %s", e)
                raise SystemExit(e)

        else:
            for airplanes_folder in AIRPLANES_FOLDERS:
                if os.path.exists("/run/" + airplanes_folder + "/aircraft.json"):
                    with open(
                        "/run/" + airplanes_folder + "/aircraft.json"
                    ) as json_file:
                        logger.debug(
                            "Loading data from file: %s ",
                            "/run/" + airplanes_folder + "/aircraft.json",
                        )
                        data = json.load(json_file)
                        planes = data["aircraft"]
                        dt_stamp = data["now"]
                        logger.debug("Found TimeStamp %s", dt_stamp)
                        break
                else:
                    logger.info(
                        "File not Found: %s",
                        "/run/" + airplanes_folder + "/aircraft.json",
                    )

        if data == "" or data is None:
            logger.error("No aircraft data read")
            sys.exit()

        # dt_stamp = data.json()["now"]
        # logger.debug("Found TimeStamp %s", dt_stamp)
        # planes = data.json()["aircraft"]

    except (ValueError, UnboundLocalError, AttributeError) as err:
        logger.error("JSON Decode Error: %s", err)
        sys.exit()

    logger.debug("Aircraft to check: %d", len(planes))

    for plane in planes:
        output = ""

        # There is a ts in the json output - should we use that?
        #        dt = ts = datetime.datetime.now().timestamp()
        # dt_stamp = datetime.datetime.now().timestamp()

        output += str(dt_stamp)
        callsign = ""
        heli_type = ""

        try:
            iaco_hex = str(plane["hex"]).lower()
            heli_type = find_helis(iaco_hex)
            output += " " + heli_type
        except BaseException:
            output += " no type or reg"

        if "category" in plane and plane["category"] == "A7":
            if "flight" in plane:
                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s type: %s",
                    iaco_hex,
                    plane["category"],
                    str(plane["flight"]).strip(),
                    heli_type or "Unknown",
                )
            else:
                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s type: %s",
                    iaco_hex,
                    plane["category"],
                    "no_call",
                    heli_type or "Unknown",
                )

        if heli_type == "" or heli_type is None:
            # This short circuits parsing of aircraft with unknown iaco_hex codes
            logger.debug("%s Not a known rotorcraft ", iaco_hex)
            continue

        logger.debug("Parsing Helicopter: %s", iaco_hex)

        try:
            callsign = str(plane["flight"]).strip()
            output += " " + callsign
        except BaseException:
            output += " no call"

        try:
            # Assumtion is made that negative altitude is unlikely
            # Using max() here removes negative numbers

            alt_baro = max(0, int(plane["alt_baro"]))

            # FR altitude

            output += " " + str(alt_baro)

        except BaseException:
            alt_baro = None

        try:
            alt_geom = max(0, int(plane["alt_geom"]))
            # FR altitude
            output += " " + str(alt_geom)
        except BaseException:
            alt_geom = None

        try:
            head = float(plane["r_dir"])
            # readsb/FR "track"
            output += " " + str(head)
        except BaseException:
            head = None
            output += " no heading"
        try:
            lat = float(plane["lat"])
            lon = float(plane["lon"])
            output += " " + str(lat) + "," + str(lon)

        except BaseException:
            lat = None
            lon = None
        try:
            squawk = str(plane["squawk"])
            output += " " + squawk
        except BaseException:
            squawk = ""
            output += " no squawk"

        logger.info("Heliopter Reported %s: %s", plane["hex"], output)

        if heli_type != "":
            mydict = {
                "type": "Feature",
                "properties": {
                    "date": dt_stamp,
                    "icao": iaco_hex,
                    "type": heli_type,
                    "call": callsign,
                    "heading": head,
                    "squawk": squawk,
                    "altitude_baro": alt_baro,
                    "altitude_geo": alt_geom,
                    "feeder": FEEDER_ID,
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
            ret_val = mongo_insert(mydict)
            # if ret_val: ... do something


def find_helis_old(iaco_hex):
    """
    Deprecated
    Check if an iaco hex code is in Bills catalog of DC Helicopters
    returns the type of helicopter if known
    """

    with open("bills_operators.csv", encoding="UTF-8") as csvfile:
        opsread = csv.DictReader(csvfile)
        heli_type = ""
        for row in opsread:
            if iaco_hex.upper() == row["hex"]:
                heli_type = row["type"]
        return heli_type


def find_helis(iaco_hex):
    """
    check if iaco is known and return type or empty string
    """
    logger.debug("Checking for: %s", iaco_hex)
    if heli_types[iaco_hex]:
        return heli_types[iaco_hex]

    return ""


def load_helis_from_url(bills_url):
    """
    Loads helis dictionary with bills_operators pulled from URL
    """
    helis_dict = {}

    try:
        bills = requests.get(bills_url, timeout=7.5)
    except requests.exceptions.RequestException as e:
        raise

    logger.debug("Request returns Status_Code: %s", bills.status_code)

    if bills.status_code == 200:
        tmp_bills_age = time()
        # Saving Copy for subsequent operations
        # Note: it would be best if we were in the right directory before we tried to write
        with open("bills_operators_tmp.csv", "w", encoding="UTF-8") as tmpcsvfile:
            try:
                tmpcsvfile.write(bills.text)
                tmpcsvfile.close()
                old_bills_age = check_bills_age()
                if old_bills_age > 0:
                    os.rename(
                        "bills_operators.csv",
                        "bills_operators_" + strftime("%Y%m%d-%H%M%S") + ".csv",
                    )
                os.rename("bills_operators_tmp.csv", "bills_operators.csv")
                logger.info(
                    "Bills File Updated from web at %s",
                    ctime(tmp_bills_age),
                )
            except Exception as err_except:
                logger.error("Got error %s", err_except)
                raise

        opsread = csv.DictReader(bills.text.splitlines())
        for row in opsread:
            # print(row)
            helis_dict[row["hex"].lower()] = row["type"]
            logger.debug("Loaded %s :: %s", row["hex"].lower(), row["type"])
        return (helis_dict, bills_age)
    # else:
    logger.warning(
        "Could not Download bills_operators - status_code: %s", bills.status_code
    )
    return (None, None)


def load_helis_from_file():
    """
    Read Bills catalog of DC Helicopters into array
    returns dictionary of helis and types
    """
    helis_dict = {}

    bills_age = check_bills_age()

    if bills_age == 0:
        logger.warning("Warning: bills_operators.csv Not found")

    if datetime.datetime.now().timestamp() - bills_age > 86400:
        logger.warning(
            "Warning: bills_operators.csv more than 24hrs old: %s", ctime(bills_age)
        )

    logger.debug("Bills Age: %s", bills_age)

    with open(bills_operators, encoding="UTF-8") as csvfile:
        opsread = csv.DictReader(csvfile)
        for row in opsread:
            helis_dict[row["hex"].lower()] = row["type"]
            logger.debug("Loaded %s :: %s", row["hex"].lower(), row["type"])
        return (helis_dict, bills_age)


def check_bills_age():
    """
    Checks age of file - returns zero if File not Found
    """
    try:
        bills_age = os.path.getmtime(bills_operators)

    except FileNotFoundError:
        bills_age = 0

    return bills_age


def run_loop(interval, h_types):
    """
    Run as loop and sleep specified interval
    """

    while True:
        logger.debug("Starting Update")

        bills_age = check_bills_age()

        if int(time() - bills_age) >= (BILLS_TIMEOUT - 60):  # Timeout - 1 minute
            logger.debug(
                "bills_operators.csv not found or older than timeout value: %s",
                ctime(bills_age),
            )
            (h_types, bills_age) = load_helis_from_url(BILLS_URL)
            logger.info("Updated bills_operators.csv at: %s", ctime(bills_age))
        else:
            logger.debug(
                "bills_operators.csv less than timeout value old - last updated at: %s",
                ctime(bills_age),
            )

        update_helidb()

        logger.debug("sleeping %s...", interval)

        sleep(interval)


if __name__ == "__main__":
    # Read Environment
    # Need to be smarter about where this is located.

    parser = argparse.ArgumentParser(description="Helicopters of DC data loader")
    parser.add_argument(
        "-V",
        "--version",
        help="Print version and exit",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Emit Verbose message stream",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-D", "--debug", help="Emit Debug messages", action="store_true", default=False
    )

    parser.add_argument(
        "-d", "--daemon", help="Run as a daemon", action="store_true", default=False
    )

    parser.add_argument(
        "-o", "--once", help="Run once and exit", action="store_true", default=False
    )

    parser.add_argument(
        "-l",
        "--log",
        help="File for logging reported rotorcraft",
        action="store",
        default=None,
    )

    parser.add_argument(
        "-w",
        "--web",
        help="Download / Update Bills Operators from Web on startup (defaults to reading local file)",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "-i",
        "--interval",
        help="Interval between cycles in seconds",
        action="store",
        type=int,
        default=60,
    )

    parser.add_argument(
        "-s",
        "--server",
        help="dump1090 server hostname (default localhost)",
        nargs=1,
        action="store",
        default=None,
    )

    parser.add_argument(
        "-p",
        "--port",
        help="alt-http port on dump1090 server (default 8080)",
        action="store",
        type=int,
        default=None,
    )

    parser.add_argument(
        "-u", "--mongouser", help="MONGO DB User", action="store", default=None
    )
    parser.add_argument(
        "-P", "--mongopw", help="Mongo DB Password", action="store", default=None
    )
    parser.add_argument(
        "-f", "--feederid", help="Feeder ID", action="store", default=None
    )

    parser.add_argument(
        "-r",
        "--readlocalfiles",
        help="Check for aircraft.json files under /run/... ",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    if args.version:
        print("{parser.prog} version: {VERSION}")
        sys.exit()

    logging.basicConfig(level=logging.WARN)

    if args.verbose or args.log:
        #        ch=logging.StreamHandler()
        #        ch.setLevel(logging.INFO)
        #        logger.addHandler(ch)
        #
        # args.log also sets args.verbose so theres something to log

        logger.setLevel(logging.INFO)

    if args.debug:
        #        ch=logging.StreamHandler()
        #        ch.setLevel(logging.DEBUG)
        #        logger.addHandler(ch)

        logger.setLevel(logging.DEBUG)

    if args.log:
        # opens a second logging instance specifically for logging noted copters "output"
        logger.debug("Adding FileHandler to logger with filename %s", args.log)
        # copter_logger = logging.getLogger('copter_logger')
        cl = logging.FileHandler(args.log)
        cl.setFormatter(formatter)
        cl.setLevel(logging.INFO)

        logger.addHandler(cl)

    # once logging is setup we can read the environment

    for conf_folder in CONF_FOLDERS:
        conf_folder = os.path.expanduser(conf_folder)
        conf_folder = os.path.abspath(conf_folder)
        # .env is probably not unique enough to search for
        if os.path.exists(os.path.join(conf_folder, ".env")) and os.path.exists(
            os.path.join(conf_folder, ".bills_operators.csv")
        ):
            logger.debug("Conf folder found: %s", conf_folder)
            break

    env_file = os.path.join(conf_folder, ".env")

    bills_operators = os.path.join(conf_folder, "bills_operators.csv")

    config = dotenv_values(env_file)

    # Should be pulling these from env

    if (
        "API-KEY" in config
        and config["API-KEY"] != "BigLongRandomStringOfLettersAndNumbers"
    ):
        logger.debug("Mongo API Key found - using https api ")
        MONGO_API_KEY = config["API-KEY"]
        mongo_insert = mongo_https_insert
    else:
        if args.mongopw:
            MONGOPW = args.mongopw
        elif "MONGOPW" in config:
            MONGOPW = config["MONGOPW"]
        else:
            MONGOPW = None
            logger.error("No Mongo PW Found - Exiting")
            sys.exit()

        if args.mongouser:
            MONGOUSER = args.mongouser
        elif "MONGOUSER" in config:
            MONGOUSER = config["MONGOUSER"]
        else:
            MONGOUSER = None
            logger.error("No Mongo User Found - Exiting")
            sys.exit()

        logger.debug("Mongo User and Password found - using MongoClient")
        mongo_insert = mongo_client_insert

    if args.feederid:
        FEEDER_ID = args.feederid
    elif "FEEDER_ID" in config:
        FEEDER_ID = config["FEEDER_ID"]
    else:
        FEEDER_ID = None
        logger.error(
            "No FEEDER_ID defined in command line options or .env file - Exiting"
        )
        sys.exit()

    if args.readlocalfiles:
        logger.debug("Using Local json files")
        AIRCRAFT_URL = None
        server = None
        port = None

    else:
        if args.server:
            server = args.server
        elif "SERVER" in config:
            server = config["SERVER"]
        else:
            server = "localhost"
        if args.port:
            port = args.port
        elif "PORT" in config:
            port = config["PORT"]
        else:
            port = 8080

    if server and port:
        AIRCRAFT_URL = f"http://{server}:{port}/data/aircraft.json"
        logger.debug("Using AIRCRAFT_URL: %s", AIRCRAFT_URL)
    else:
        AIRCRAFT_URL = None
        logger.debug("AIRCRAFT_URL set to None")

    # probably need to have an option for different file names

    heli_types = {}

    logger.debug("Using bills_operators as : %s", bills_operators)

    bills_age = check_bills_age()

    if args.web:
        logger.debug("Loading bills_operators from URL: %s ", BILLS_URL)
        (heli_types, bills_age) = load_helis_from_url(BILLS_URL)
        logger.info("Loaded bills_operators from URL: %s ", BILLS_URL)

    elif bills_age > 0:
        logger.debug("Loading bills_operators from file: %s ", bills_operators)
        (heli_types, bills_age) = load_helis_from_file()
        logger.info("Loaded bills_operators from file: %s ", bills_operators)

    else:
        logger.error("Bills Operators file not found at %s -- exiting", bills_operators)
        raise FileNotFoundError

    logger.info("Loaded %s helis from Bills", str(len(heli_types)))

    if args.once:
        update_helidb()
        sys.exit()

    if args.daemon:
        #         going to need to add something this to keep the logging going
        # see: https://stackoverflow.com/questions/13180720/maintaining-logging-and-or-stdout-stderr-in-python-daemon
        #                   files_preserve = [ cl.stream,], ):
        #

        log_handles = []
        for handler in logger.handlers:
            log_handles.append(handler.stream.fileno())

        #        if logger.parent:
        #            log_handles += getLogFileHandles(logger.parent)

        with daemon.DaemonContext(files_preserve=log_handles):
            run_loop(args.interval, heli_types)

    else:
        try:
            logger.debug("Starting main processing loop")
            run_loop(args.interval, heli_types)

        except KeyboardInterrupt:
            logger.warning("Received Keyboard Interrupt -- Exiting...")
            sys.exit()
