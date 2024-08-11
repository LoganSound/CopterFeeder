#!/usr/bin/env python3

"""
Upload rotorcraft positions to Helicopters of DC
"""

import json
import csv

# unused

# from datetime import timezone

# import datetime
import logging
import argparse
import sys
import os
from time import sleep, ctime, time, strftime, gmtime
import signal

import requests
import daemon

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from prometheus_client import start_http_server, Gauge, Summary

# used for getting MONGOPW and MONGOUSER
from dotenv import dotenv_values  # , set_key


# only need one of these
import pymongo

# from pymongo import MongoClient


## YYYYMMDD_HHMM_REV
VERSION = "202408110938_001"

# Bills

BILLS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv"

#BILLS_TIMEOUT = 86400  # In seconds - Standard is 1 day
BILLS_TIMEOUT = 3600  # Standard is 1 hour as of 20240811


# Default Mongo URL
# See -M option in arg parse section
#    "https://us-central1.gcp.data.mongodb-api.com/app/feeder-puqvq/endpoint/feedadsb"
MONGO_URL = "https://us-central1.gcp.data.mongodb-api.com/app/feeder-puqvq/endpoint/feedadsb_2023"

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


# Prometheus

PROM_PORT = 8999

update_heli_time = Summary(
    "update_heli_processing_seconds", "Time spent updating heli db"
)


formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

# logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.basicConfig(format="%(asctime)s - %(module)s - %(levelname)s - %(message)s")

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
    "adsb-feeder-ultrafeeder/readsb",
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

    try:
        response = requests.post(MONGO_URL, headers=headers, json=mydict, timeout=7.5)
        response.raise_for_status()
        logger.debug("Response: %s", response)
        logger.info("Mongo Insert Status: %s", response.status_code)

    except requests.exceptions.HTTPError as e:
        logger.warning("Mongo Post Error: %s ", e.response.text)

    return response.status_code


def dump_recents(signum=signal.SIGUSR1, frame=""):
    """Dump recents if we get a sigusr1"""
    signame = signal.Signals(signum).name
    logger.info(f"Signal handler dump_recents called with signal {signame} ({signum})")

    logger.info("Dumping %d entries...", len(recent_flights))

    for hex_icao in sorted(recent_flights):
        logger.info(
            "hex_icao: %s flight: %s seen: %d",
            hex_icao,
            recent_flights[hex_icao][0],
            recent_flights[hex_icao][1],
        )


@update_heli_time.time()
def update_helidb():
    """Main"""

    # local_time = datetime.now().astimezone()

    logger.info(
        "Updating Helidb at %s ",
        datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z %z"),
    )

    # Set the signal handler to dump recents

    signal.signal(signal.SIGUSR1, dump_recents)

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
                    # "now" is a 10.1 digit seconds since the epoch timestamp
                    dt_stamp = data.json()["now"]
                    logger.debug("Found TimeStamp %s", dt_stamp)
                    planes = data.json()["aircraft"]

            except requests.exceptions.RequestException as e:
                logger.error(
                    "Got ConnectionError trying to request URL %s - sleeping 30", e
                )
                # raise SystemExit(e)
                sleep(30)
                return e

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
                        # "now" is a 10.1 digit seconds since the epoch timestamp
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
            return None
            # sys.exit()

        # dt_stamp = data.json()["now"]
        # logger.debug("Found TimeStamp %s", dt_stamp)
        # planes = data.json()["aircraft"]

    except (ValueError, UnboundLocalError, AttributeError) as err:
        logger.error("JSON Decode Error: %s", err)
        return err
        # sys.exit()

    logger.debug("Aircraft to check: %d", len(planes))

    for plane in planes:
        output = ""
        # aircrafts.json documented here (and elsewhere):
        # https://github.com/flightaware/dump1090/blob/master/README-json.md
        #
        # There is a ts in the json output - should we use that?
        #        dt = ts = datetime.datetime.now().timestamp()
        # dt_stamp = datetime.datetime.now().timestamp()

        output += str(dt_stamp)
        callsign = ""
        heli_type = ""
        heli_tail = ""

        try:
            icao_hex = str(plane["hex"]).lower()
            # heli_type = find_helis(icao_hex)
            heli_type = search_bills(icao_hex, "type")
            heli_tail = search_bills(icao_hex, "tail")
            output += " " + heli_type + " " + heli_tail
        except BaseException:
            output += " no type or reg"

        if search_bills(icao_hex, "hex") != None:
            logger.debug("%s found in Bills", icao_hex)
        else:
            logger.debug("%s not found in Bills", icao_hex)

        if "category" in plane:
            category = plane["category"]
        else:
            category = "Unk"

        if "flight" in plane:
            callsign = str(plane["flight"]).strip()
        else:
            # callsign = "no_call"
            # callsign = ""
            callsign = None

        # Should identify anything reporting itself as Wake Category A7 / Rotorcraft or listed in Bills
        if (search_bills(icao_hex, "hex") != None) or category == "A7":

            if icao_hex not in recent_flights:
                recent_flights[icao_hex] = [callsign, 1]
                logger.debug(
                    "Added %s to recents (%d) as %s",
                    icao_hex,
                    len(recent_flights),
                    callsign,
                )
            elif (
                icao_hex in recent_flights
                and recent_flights[icao_hex][0] != callsign
                # and callsign != "no_call"
                # and callsign != ""
                and callsign != None
            ):
                logger.debug(
                    "Updating %s in recents as: %s - was:  %s",
                    icao_hex,
                    callsign,
                    recent_flights[icao_hex][0],
                )
                recent_flights[icao_hex] = [callsign, recent_flights[icao_hex][1] + 1]

            else:
                # increment the count
                recent_flights[icao_hex][1] += 1

                logger.debug(
                    "Incrmenting %s callsign %s to %d",
                    icao_hex,
                    recent_flights[icao_hex][0],
                    recent_flights[icao_hex][1],
                )

            if icao_hex in recent_flights:

                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s tail: %s type: %s seen: %d times",
                    icao_hex,
                    category,
                    recent_flights[icao_hex][0],
                    heli_tail or "Unknown",
                    heli_type or "Unknown",
                    recent_flights[icao_hex][1],
                )

            else:
                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s tail: %s type: %s",
                    icao_hex,
                    category,
                    "(null)",
                    heli_tail or "Unknown",
                    heli_type or "Unknown",
                )

        if heli_type == "" or heli_type is None:
            # This short circuits parsing of aircraft with unknown icao_hex codes
            logger.debug("%s Not a known rotorcraft ", icao_hex)
            continue

        logger.debug("Parsing Helicopter: %s", icao_hex)

        try:
            callsign = str(plane["flight"]).strip()
            output += " " + callsign
        except BaseException:
            output += " no call (" + heli_tail + ")"

        try:
            # Assumtion is made that negative altitude is unlikely
            # Using max() here removes negative numbers

            alt_baro = max(0, int(plane["alt_baro"]))

            # FR altitude

            output += " altbaro " + str(alt_baro)

        except BaseException:
            alt_baro = None

        try:
            alt_geom = max(0, int(plane["alt_geom"]))
            # FR altitude
            output += " altgeom " + str(alt_geom)

        except BaseException:
            alt_geom = None

        try:
            # head = float(plane["r_dir"])
            head = float(plane["track"])
            # readsb/FR "track"
            output += " head " + str(head)

        except BaseException:
            head = None
            output += " no heading"

        try:
            lat = float(plane["lat"])
            lon = float(plane["lon"])

            output += " Lat: " + str(lat) + ", Lon: " + str(lon)

            geometry = [lon, lat]

        except BaseException:
            lat = None
            lon = None
            # this should cleanup null issue #9 for mongo
            # updated 20240228 per discussion with SR
            # geometry = None
            geometry = [None, None]
            output += " Lat: " + str(lat) + ", Lon: " + str(lon)
            logger.info("No Lat/Lon - Not reported: %s: %s", plane["hex"], output)
            continue

        try:
            groundspeed = float(plane["gs"])
            output += " gs " + str(groundspeed)

        except BaseException:
            groundspeed = None

        try:
            rssi = float(plane["rssi"])
            output += " rssi " + str(rssi)

        except BaseException:
            rssi = None

        try:
            squawk = str(plane["squawk"])
            output += " " + squawk

        except BaseException:
            # squawk = ""
            squawk = None
            output += " no squawk"

        logger.info("Heli Reported %s: %s", plane["hex"], output)

        if heli_type != "":
            utc_time = datetime.fromtimestamp(dt_stamp, tz=timezone.utc)
            est_time = utc_time.astimezone(ZoneInfo("America/New_York"))

            mydict = {
                "type": "Feature",
                "properties": {
                    "date": dt_stamp,
                    # "date": utc_time,
                    "icao": icao_hex,
                    "type": heli_type,
                    "tail": heli_tail,
                    "call": callsign,
                    "heading": head,
                    "squawk": squawk,
                    "altitude_baro": alt_baro,
                    "altitude_geo": alt_geom,
                    "groundspeed": groundspeed,
                    "rssi": rssi,
                    "feeder": FEEDER_ID,
                    "readableTime": f"{est_time.strftime('%Y-%m-%d %H:%M:%S')} ({est_time.strftime('%I:%M:%S %p')})",
                },
                "geometry": {"type": "Point", "coordinates": geometry},
            }
            ret_val = mongo_insert(mydict)
            # return ret_val
            logger.debug("Mongo_insert return: %s ", ret_val)
            # if ret_val: ... do something


def find_helis_old(icao_hex):
    """
    Deprecated
    Check if an icao hex code is in Bills catalog of DC Helicopters
    returns the type of helicopter if known
    """

    with open("bills_operators.csv", encoding="UTF-8") as csvfile:
        opsread = csv.DictReader(csvfile)
        heli_type = ""
        for row in opsread:
            if icao_hex.upper() == row["hex"]:
                heli_type = row["type"]
        return heli_type


def find_helis(icao_hex):
    """
    check if icao is known and return type or empty string
    """
    logger.debug("Checking for: %s", icao_hex)
    if heli_types[icao_hex]["type"]:
        return heli_types[icao_hex]["type"]

    return ""


def search_bills(icao_hex, column_name):
    """
    check if icao is known return callsign or empty string
    """
    logger.debug("Checking for: %s", icao_hex)
    if icao_hex in heli_types:
        if heli_types[icao_hex][column_name]:
            return heli_types[icao_hex][column_name]
        else:
            return ""
    else:
        return None


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
                if os.path.exists("bills_operators.csv"):
                    old_bills_age = check_bills_age()
                else:
                    old_bills_age = 0

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
            # helis_dict[row["hex"].lower()] = row["type"]
            helis_dict[row["hex"].lower()] = row
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

    if datetime.now().timestamp() - bills_age > 86400:
        logger.warning(
            "Warning: bills_operators.csv more than 24hrs old: %s", ctime(bills_age)
        )

    logger.debug("Bills Age: %s", bills_age)

    with open(bills_operators, encoding="UTF-8") as csvfile:
        opsread = csv.DictReader(csvfile)
        for row in opsread:
            # helis_dict[row["hex"].lower()] = row["type"]
            helis_dict[row["hex"].lower()] = row
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


def init_prometheus():
    global tx
    global update_heli_time

    tx = Gauge(
        f"switch_interface_tx_packets",
        "Total transmitted packets on interface",
        ["host", "id"],
    )

    tx.labels("foo", "bar").set(0)
    tx.labels("boo", "baz").set(0)


# Decorate function with metric.
# @update_heli_time.time()
# def process_prometheus(t):
#     """A dummy function that takes some time."""
#     tx.labels("foo", "bar").inc()
#     tx.labels("boo", "baz").inc()
#     sleep(t)


def run_loop(interval, h_types):
    """
    Run as loop and sleep specified interval
    """
    dump_clock = 0
    # process_prometheus(random.random())
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

        if dump_clock >= 60:
            dump_recents(signal.SIGUSR1, "")
            dump_clock = 0
        else:
            logger.debug("dump_clock = %d ", dump_clock)
            dump_clock += 1

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
        "-M",
        "--mongourl",
        help="MONGO DB Endpoint URL",
        action="store",
        default=MONGO_URL,
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

    if "MONGO_URL" in config:
        MONGO_URL = config["MONGO_URL"]

    elif args.mongourl:
        MONGO_URL = args.mongourl

    else:
        MONGO_URL = None
        logger.error("No Mongo Endpoint URL Found - Exiting")
        sys.exit()

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
    recent_flights = {}

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
            init_prometheus()
            start_http_server(PROM_PORT)
            run_loop(args.interval, heli_types)

    else:
        try:
            logger.debug("Starting main processing loop")
            init_prometheus()
            start_http_server(PROM_PORT)
            run_loop(args.interval, heli_types)

        except KeyboardInterrupt:
            logger.warning("Received Keyboard Interrupt -- Exiting...")
            sys.exit()
