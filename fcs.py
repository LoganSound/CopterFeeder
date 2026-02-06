#!/usr/bin/env python3

"""
Upload rotorcraft positions to Helicopters of DC
"""

# Standard library imports
import argparse
import atexit
import csv
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from threading import Lock
from time import ctime, gmtime, sleep, strftime, time
from zoneinfo import ZoneInfo

# Third party imports
import daemon
import requests
import validators
from dotenv import dotenv_values
from prometheus_client import Counter, Gauge, Summary, start_http_server
from pymongo import MongoClient, monitoring
from pymongo.errors import ConnectionFailure, OperationFailure

from icao_heli_types import icao_heli_types

# import __version__

## YYYYMMDD_HHMM_REV
CODE_DATE = "20250316"
VERSION = "25.2.12"


FEEDER_ID: str | None = None

DEFAULT_MONGO_APP_NAME = "CopterFeeder"

_mongo_client: MongoClient | None = None
_mongo_client_key: tuple[str, str] | None = None  # (mongo_uri, mongo_app_name)

DEFAULT_MONGO_CONN_LOG_ENABLED = True
DEFAULT_MONGO_CONN_LOG_INTERVAL_SECS = 60

MONGO_CONN_LOG_ENABLED = DEFAULT_MONGO_CONN_LOG_ENABLED
MONGO_CONN_LOG_INTERVAL_SECS = DEFAULT_MONGO_CONN_LOG_INTERVAL_SECS
MONGO_CONN_TRACKING_ACTIVE = False
_mongo_conn_log_next_ts = 0.0


class MongoConnectionTracker:
    """Track current and lifetime MongoClient connection counts."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._open_connections_current = 0
        self._connections_opened_total = 0
        self._connections_closed_total = 0

    def connection_opened(self) -> None:
        with self._lock:
            self._open_connections_current += 1
            self._connections_opened_total += 1

    def connection_closed(self) -> None:
        with self._lock:
            self._connections_closed_total += 1
            self._open_connections_current = max(0, self._open_connections_current - 1)

    def snapshot(self) -> tuple[int, int, int]:
        with self._lock:
            return (
                self._open_connections_current,
                self._connections_opened_total,
                self._connections_closed_total,
            )


class MongoConnectionPoolListener(monitoring.ConnectionPoolListener):
    """CMAP listener used to maintain per-process connection counters."""

    def connection_created(self, event) -> None:
        _mongo_connection_tracker.connection_opened()

    def connection_closed(self, event) -> None:
        _mongo_connection_tracker.connection_closed()


_mongo_connection_tracker = MongoConnectionTracker()
_mongo_connection_listener = MongoConnectionPoolListener()

# Bills

BILLS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv"

# BILLS_TIMEOUT = 86400  # In seconds - Standard is 1 day
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

fcs_update_heli_time = Summary(
    "helicopter_db_update_duration_seconds",
    "Time spent processing and updating the helicopter database in seconds",
    ["feeder_id"],
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
    "/app/data",
]

# Hard Coding User/Pw etc is bad umkay
# Should be pulling thse from env
#    FEEDER_ID = ""
#    AIRPLANES_FOLDER = "adsbexchange-feed"
#    # FR24: dump1090-mutability
#    # ADSBEXchange location: adsbexchange-feed
#    # Readsb location: readsb
#    # MONGOUSER = ""
#    # MONGOPW = ""


# Deprecated with "requests" pull to localhost:8080
# AIRPLANES_FOLDER = "dump1090-fa"
# FR24: dump1090-mutability
# ADSBEXchange location: adsbexchange-feed
# Readsb location: readsb


def build_mongo_uri() -> str:
    """
    Build a MongoDB connection URI from configured globals.

    Note:
        We intentionally do not set appName in the URI. Use MongoClient(appname=...)
        so the value is a single source of truth and easier to override for Atlas.
    """
    return (
        "mongodb+srv://"
        + MONGOUSER
        + ":"
        + MONGOPW
        + "@helicoptersofdc-2023.a2cmzsn.mongodb.net/"
        + "?retryWrites=true&w=majority"
    )


def get_mongo_client(mongo_uri: str, mongo_app_name: str) -> MongoClient:
    """
    Return a process-wide MongoClient, creating it once and reusing pooled connections.
    """
    global _mongo_client, _mongo_client_key

    desired_key = (mongo_uri, mongo_app_name)
    if _mongo_client is None or _mongo_client_key != desired_key:
        if _mongo_client is not None:
            try:
                _mongo_client.close()
            except Exception:
                pass

        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            retryWrites=True,
            appname=mongo_app_name,
            event_listeners=[_mongo_connection_listener],
        )

        # Fail fast on initial connect; avoids per-insert ping.
        try:
            client.admin.command("ping")
        except Exception:
            try:
                client.close()
            except Exception:
                pass
            raise

        _mongo_client = client
        _mongo_client_key = desired_key
        logger.info("MongoClient created/reused; appname=%s", mongo_app_name)

    return _mongo_client


def close_mongo_client() -> None:
    global _mongo_client, _mongo_client_key
    if _mongo_client is None:
        return
    try:
        _mongo_client.close()
        logger.debug("MongoClient closed")
    except Exception:
        logger.debug("Error closing MongoClient", exc_info=True)
    finally:
        _mongo_client = None
        _mongo_client_key = None


def parse_bool_config(value, default: bool = True) -> bool:
    """
    Parse common truthy/falsey values from environment-style configuration.
    """
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def parse_positive_int_config(value, default: int, setting_name: str) -> int:
    """
    Parse a positive integer configuration value with a safe fallback.
    """
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        if parsed <= 0:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s value '%s'; falling back to %d",
            setting_name,
            value,
            default,
        )
        return default


def emit_mongo_connection_stats_if_due(now_ts: float | None = None) -> None:
    """
    Periodically emit process-level Mongo connection counts.
    """
    global _mongo_conn_log_next_ts

    if not MONGO_CONN_TRACKING_ACTIVE or not MONGO_CONN_LOG_ENABLED:
        return

    if now_ts is None:
        now_ts = time()

    if now_ts < _mongo_conn_log_next_ts:
        return

    _mongo_conn_log_next_ts = now_ts + max(1, MONGO_CONN_LOG_INTERVAL_SECS)
    open_current, opened_total, closed_total = _mongo_connection_tracker.snapshot()

    logger.info(
        "Mongo Connections feeder_id=%s open_connections_current=%d connections_opened_total=%d connections_closed_total=%d",
        FEEDER_ID,
        open_current,
        opened_total,
        closed_total,
    )


def mongo_client_insert(mydict, dbFlags):
    """
    Insert one entry into MongoDB using the MongoDB client.

    Args:
        mydict (dict): Dictionary containing the helicopter data to insert
        dbFlags (str): Flags to determine which collection to use

    Returns:
        ObjectId or None: Returns the inserted document's ID if successful, None if failed
    """
    try:
        mongo_uri = build_mongo_uri()
        myclient = get_mongo_client(mongo_uri, DEFAULT_MONGO_APP_NAME)

        # Select database and collection
        mydb = myclient["HelicoptersofDC-2023"]
        collection_name = "ADSB-mil" if dbFlags and int(dbFlags) & 1 else "ADSB"
        mycol = mydb[collection_name]

        # Insert document
        result = mycol.insert_one(mydict)

        if result.acknowledged:
            logger.info(
                "Successfully inserted document with ID: %s into %s",
                result.inserted_id,
                collection_name,
            )
            return result.inserted_id
        else:
            logger.error("Insert was not acknowledged by MongoDB")
            return None

    except ConnectionFailure as e:
        logger.error("Failed to connect to MongoDB: %s", e)
        return None
    except OperationFailure as e:
        logger.error("MongoDB operation failed: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error during MongoDB operation: %s", e)
        return None


def mongo_https_insert(mydict, dbFlags):
    """
    Insert into Mongo using HTTPS requests call
    This will be deprecated September 2024
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

    fcs_mongo_inserts.labels(
        status_code=response.status_code, feeder_id=FEEDER_ID
    ).inc()
    return response.status_code


def dump_recents(signum=signal.SIGUSR1, frame="") -> None:
    """
    Dump information about recently seen aircraft to the logs.

    This function is primarily used as a signal handler for SIGUSR1 but can also be called
    directly. It provides a summary of all aircraft currently being tracked, including their
    ICAO hex codes, flight numbers/callsigns, and how many times they've been seen.

    Args:
        signum: Signal number that triggered this handler (defaults to SIGUSR1)
        frame: Current stack frame (unused, required for signal handler interface)
    """
    try:
        # Log signal information if called as signal handler
        if signum:
            signame = signal.Signals(signum).name
            logger.info(
                f"Signal handler dump_recents called with signal {signame} ({signum})"
            )

        # Handle empty recent_flights case
        if not recent_flights:
            logger.info("No recent flights to dump")
            return

        # Log summary header with timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("=== Recent Flights Dump at %s ===", current_time)
        logger.info(
            "Total aircraft being tracked: %d since %s", len(recent_flights), start_time
        )

        # Sort and dump detailed aircraft information
        for hex_icao in sorted(recent_flights):
            flight, seen_count = recent_flights[hex_icao]
            aircraft_type = heli_types.get(hex_icao, {}).get("type", "Unknown")
            logger.info(
                f"Aircraft: {hex_icao.upper():6} | Type: {aircraft_type:4} | Flight: {(flight or 'No Callsign'):8} | Times seen: {seen_count}"
            )

        logger.info("=== End of Dump ===")

    except Exception as e:
        logger.error("Error in dump_recents: %s", str(e))
        # Re-raise if this wasn't called as a signal handler
        if not signum:
            raise


def clean_source(source) -> str:
    """
    Normalize aircraft data source identifiers to standard format.

    Args:
        source (str | None): Raw source identifier from aircraft data

    Returns:
        str: Normalized source identifier

    Source mappings:
        - None, "unknown" -> "unkn"
        - "adsb*" -> "adsb"
        - "adsr*" -> "adsr"
        - "mlat" -> "mlat"
        - "adsb_icao_nt", "mode_s" -> "modeS"
        - "tisb*" -> "tisb"
        - "adsc" -> "adsc"
        - "other" -> "other"

    Example:
        >>> clean_source("adsb_icao")
        "adsb"
        >>> clean_source(None)
        "unkn"
    """
    try:
        # Handle None or non-string input
        if source is None:
            return "unkn"

        # Ensure source is string and lowercase for comparison
        source = str(source).lower()

        # Define source mappings
        SOURCE_MAPPINGS = {
            "unknown": "unkn",
            "mlat": "mlat",
            "adsb_icao_nt": "modeS",
            "mode_s": "modeS",
            "adsc": "adsc",
            "other": "other",
        }

        # Check prefix matches first
        if source.startswith("adsb"):
            return "adsb"
        if source.startswith("adsr"):
            return "adsr"
        if source.startswith("tisb"):
            return "tisb"

        # Return mapped value or "unkn" if no match found
        return SOURCE_MAPPINGS.get(source, "unkn")

    except Exception as e:
        logger.error("Error cleaning source identifier: %s - Error: %s", source, str(e))
        return "unkn"


@fcs_update_heli_time.labels(feeder_id=FEEDER_ID).time()
def fcs_update_helidb(interval):
    """
    Process and upload rotorcraft position data to the Helicopters of DC database.

    This function is the main processing loop that:
    1. Retrieves aircraft data from either a local file or URL endpoint
    2. Filters for rotorcraft based on category or known ICAO codes
    3. Processes position and flight data
    4. Uploads valid entries to MongoDB
    5. Updates tracking metrics

    Args:
        interval (int): Maximum age in seconds for position data to be considered valid

    Returns:
        None: Function runs continuously unless an error occurs
        Exception: Returns error object if a critical error occurs during processing

    Metrics:
        - Updates Prometheus metrics for monitoring
        - Maintains recent_flights global dictionary for tracking

    Note:
        Function is decorated with @fcs_update_heli_time.time() for performance monitoring
    """

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
                data = requests.get(AIRCRAFT_URL, timeout=15)
                data.raise_for_status()
                if data.status_code == 200:
                    logger.debug("Found data at URL: %s", AIRCRAFT_URL)
                    # "now" is a 10.1 digit seconds since the epoch timestamp
                    dt_stamp = data.json()["now"]
                    logger.debug("Found TimeStamp %s", dt_stamp)
                    planes = data.json()["aircraft"]
                elif data.status_code >= 400:
                    logger.warning(
                        "Received error %d from request for aircraft.json - sleeping 30",
                        data.status_code,
                    )
                    sleep(30)
                    return None

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

        if not data:

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
        # https://github.com/wiedehopf/readsb/blob/dev/README-json.md
        #
        # There is a ts in the json output - should we use that?
        #        dt = ts = datetime.datetime.now().timestamp()
        # dt_stamp = datetime.datetime.now().timestamp()

        output += str(dt_stamp)
        callsign = None
        callsign_label = "no_call"
        call_payload = None
        heli_type = ""
        heli_tail = ""

        # if search_bills(icao_hex, "hex") is not None:
        #     logger.debug("%s found in Bills", icao_hex)
        # else:
        #     logger.debug("%s not found in Bills", icao_hex)

        try:
            icao_hex = str(plane["hex"]).lower()

        except BaseException:
            output += " Error coverting to lowercase"

        if "category" in plane:
            category = plane["category"]
        else:
            category = "Unk"

        # Should identify anything reporting itself as Wake Category A7 / Rotorcraft or listed in Bills

        if "t" in plane and plane["t"] in icao_heli_types:
            logger.debug(f"ICAO Type {plane['t']} found in icao_heli_types")
            # else:
            #   logger.debug(f"ICAO Type {plane['t']} not found in icao_heli_types")

            # if (search_bills(icao_hex, "hex") != None) or category == "A7":

            try:
                # icao_hex = str(plane["hex"]).lower()
                # heli_type = find_helis(icao_hex)
                heli_type = search_bills(icao_hex, "type")
                if heli_type is not None:
                    logger.debug(f"Using heli_type from bills: {heli_type}")
                elif "t" in plane and plane["t"] != "":
                    heli_type = str(plane["t"])
                    add_to_htypes(icao_hex, "type", heli_type)
                    add_to_htypes(icao_hex, "src", "spot")
                    logger.debug(f"Using heli_type from aircraft.json: {heli_type}")
                # heli_tail = search_bills(icao_hex, "tail")
                else:
                    heli_type = "no type"
                    logger.debug(f"No heli_type identified: {heli_type}")
                output += " " + heli_type

            except BaseException:
                output += " no type "

            try:
                # icao_hex = str(plane["hex"]).lower()
                # heli_type = find_helis(icao_hex)
                # heli_type = search_bills(icao_hex, "type")

                heli_tail = str(plane.get("r", "")).strip()

                # If no registration found in aircraft data, check bills database
                if not heli_tail:
                    heli_tail = search_bills(icao_hex, "tail")
                    if heli_tail:
                        logger.debug(
                            "Using registration from bills database for %s: %s",
                            icao_hex,
                            heli_tail,
                        )
                else:
                    logger.debug(
                        "Using registration from aircraft data for %s: %s",
                        icao_hex,
                        heli_tail,
                    )

                # If still no registration found, use default value
                if not heli_tail:
                    heli_tail = "no reg"
                    logger.debug(
                        "No registration found for %s, using default", icao_hex
                    )

                output += f" {heli_tail}"

            except Exception as e:
                logger.error(
                    "Error processing registration for %s: %s", icao_hex, str(e)
                )
                heli_tail = "no reg"
                output += " no reg"

            raw_flight = str(plane.get("flight", "")).strip()
            if raw_flight:
                callsign = raw_flight
                callsign_label = raw_flight
                call_payload = raw_flight
                logger.debug("Flight: %s", callsign)
            else:
                # callsign = "no_call"
                # callsign = ""
                # callsign = None
                callsign = None
                callsign_label = "no_call"
                call_payload = None

            if "dbFlags" in plane:
                dbFlags = plane["dbFlags"]
            else:
                dbFlags = None

            if "ownOp" in plane:
                ownOp = plane["ownOp"]
            else:
                ownOp = None

            if icao_hex not in recent_flights:
                recent_flights[icao_hex] = [callsign_label, 1]
                logger.debug(
                    "Added %s to recents (%d) as %s",
                    icao_hex,
                    len(recent_flights),
                    callsign_label,
                )
                fcs_rx.labels(
                    icao=icao_hex, cs=callsign_label, feeder_id=FEEDER_ID
                ).inc(1)
            elif (
                icao_hex in recent_flights
                and recent_flights[icao_hex][0] != callsign_label
            ):
                logger.debug(
                    "Updating %s in recents as: %s - was:  %s",
                    icao_hex,
                    callsign_label,
                    recent_flights[icao_hex][0],
                )
                recent_flights[icao_hex] = [
                    callsign_label,
                    recent_flights[icao_hex][1] + 1,
                ]
                fcs_rx.labels(
                    icao=icao_hex, cs=callsign_label, feeder_id=FEEDER_ID
                ).inc(1)

            else:
                # increment the count
                recent_flights[icao_hex][1] += 1
                # Prometheus counter
                fcs_rx.labels(
                    icao=icao_hex, cs=callsign_label, feeder_id=FEEDER_ID
                ).inc(1)

                logger.debug(
                    "Incrmenting %s callsign %s to %d",
                    icao_hex,
                    recent_flights[icao_hex][0],
                    recent_flights[icao_hex][1],
                )

            if icao_hex in recent_flights:

                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s tail: %s type: %s dbFlags: %s seen: %d times",
                    icao_hex,
                    category,
                    recent_flights[icao_hex][0],
                    heli_tail or "Unknown",
                    heli_type or "Unknown",
                    dbFlags,
                    recent_flights[icao_hex][1],
                )

            else:
                logger.info(
                    "Aircraft: %s is rotorcraft - Category: %s flight: %s tail: %s type: %s dbFlag: %s",
                    icao_hex,
                    category,
                    "(null)",
                    heli_tail or "Unknown",
                    heli_type or "Unknown",
                    dbFlags,
                )
        else:
            logger.debug("%s Not a rotorcraft ", icao_hex)
            continue

        # if not heli_type or heli_type is None:
        # if not heli_type:
        #     # This short circuits parsing of aircraft with unknown icao_hex codes

        #     logger.debug("%s Not a known rotorcraft ", icao_hex)
        #     continue

        logger.debug("Parsing Helicopter: %s", icao_hex)

        try:
            # seen_pos is an offset in seconds from "now" time to when last position was seen
            if "seen_pos" in plane:
                seen_pos = float(plane["seen_pos"])
            else:
                seen_pos = 0
            logger.debug(f"seen_pos: {seen_pos:.2f}")

        except BaseException:
            logger.warning("seen_pos error")

        if seen_pos > interval:
            logger.info(
                f"Seen_pos ({seen_pos:.2f}) > interval ({interval}): skipping {icao_hex} "
            )
            continue

        try:
            # note that this is somewhat redundant to callsign processing before being in this if stanza
            # if "flight" in plane and not callsign or callsign is None:
            if not callsign:
                # should never get here - should be handled above
                logger.warning("Callsign is empty or None")
                callsign_label = "no_call"

            output += " <" + callsign_label + ">"
        except BaseException:
            logger.debug("No 'flight' field or bad callsign data")
            callsign_label = "no_call"
            output += " <no_call>"

        try:
            # Assumtion is made that negative altitude is unlikely
            # Using max() here removes negative numbers

            alt_baro = max(0.0, float(plane["alt_baro"]))

            # FR altitude

            output += " altbaro " + str(alt_baro)

        except BaseException:
            alt_baro = None

        try:
            alt_geom = max(0.0, float(plane["alt_geom"]))
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
            output += " sq " + squawk

        except BaseException:
            # squawk = ""
            squawk = None
            output += " no squawk"

        try:
            # See https://github.com/wiedehopf/readsb/blob/dev/README-json.md
            source = clean_source(str(plane["type"]))
            output += " src " + source
            fcs_sources.labels(source=source, feeder_id=FEEDER_ID).inc(1)

        except BaseException:

            source = None
            output += " no source"

        logger.info("Heli Reported %s: %s", plane["hex"], output)

        # if heli_type != "":
        if icao_hex != "":
            utc_time = datetime.fromtimestamp(dt_stamp, tz=timezone.utc)
            est_time = utc_time.astimezone(ZoneInfo("America/New_York"))

            mydict = {
                "type": "Feature",
                "properties": {
                    # Date - "now" from aircraft.json in seconds from the unix epoch format
                    # "date": dt_stamp,
                    # Corrected with seen_pos
                    "date": dt_stamp - seen_pos,
                    # jsDate - a datetime obect in utc timezone corrected by seen_pos
                    "jsDate": datetime.fromtimestamp(
                        dt_stamp - seen_pos, tz=timezone.utc
                    ),
                    # proposed but not implemented
                    # pythonDate - float seconds from the epoch corrected by seen_pos
                    # "pythonDate": dt_stamp - seen_pos,
                    #
                    # createdDate - datetime object of "now" from aircraft.json
                    "createdDate": utc_time,
                    "icao": icao_hex,
                    "type": heli_type,
                    "tail": heli_tail,
                    "call": call_payload,
                    "heading": head,
                    "squawk": squawk,
                    "altitude_baro": alt_baro,
                    "altitude_geo": alt_geom,
                    "groundspeed": groundspeed,
                    "rssi": rssi,
                    "feeder": FEEDER_ID,
                    "source": source,
                    "dbFlags": dbFlags,
                    "ownOp": ownOp,
                    # readableTime - string representation of Datetime in EST timezone
                    "readableTime": f"{est_time.strftime('%Y-%m-%d %H:%M:%S')} ({est_time.strftime('%I:%M:%S %p')})",
                },
                "geometry": {"type": "Point", "coordinates": geometry},
            }
            ret_val = mongo_insert(mydict, dbFlags)
            # return ret_val
            logger.debug("Mongo_insert return: %s ", ret_val)
            # if ret_val: ... do something


def find_helis(icao_hex) -> str | None:
    """
    Check if an ICAO hex code is in the known helicopter database and return its type.

    Args:
        icao_hex (str): The ICAO hex code to look up (case-insensitive)

    Returns:
        str | None: The helicopter type if found, None if not found

    Example:
        >>> find_helis("ac9f65")
        "MD52"
        >>> find_helis("unknown")
        None
    """
    try:
        # Ensure icao_hex is lowercase for consistent lookup
        icao_hex = str(icao_hex).lower()
        logger.debug("Checking helicopter type for ICAO: %s", icao_hex)

        # Check if ICAO exists in database and has a type
        if icao_hex in heli_types and heli_types[icao_hex].get("type"):
            return heli_types[icao_hex]["type"]

        return None

    except Exception as e:
        logger.error("Error looking up helicopter type for %s: %s", icao_hex, str(e))
        return None


def add_to_htypes(icao_hex: str, column_name: str, value: str) -> bool:
    """
    Add or update a value in the helicopter types dictionary.

    Args:
        icao_hex (str): The ICAO hex code of the aircraft (case-insensitive)
        column_name (str): The name of the field to add/update (e.g., 'type', 'tail')
        value (str): The value to store

    Returns:
        bool: True if operation was successful, False if an error occurred

    Example:
        >>> add_to_htypes('ac9f65', 'type', 'MD52')
        True
        >>> add_to_htypes('invalid!', 'type', 'MD52')
        False
    """
    try:
        # Validate inputs
        if not isinstance(icao_hex, str) or not icao_hex.strip():
            raise ValueError("ICAO hex code must be a non-empty string")
        if not isinstance(column_name, str) or not column_name.strip():
            raise ValueError("Column name must be a non-empty string")
        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        # Normalize ICAO hex code to lowercase
        icao_hex = icao_hex.lower().strip()

        # Initialize dictionary for new ICAO or update existing entry
        if icao_hex not in heli_types:
            heli_types[icao_hex] = {column_name: value}
        else:
            heli_types[icao_hex][column_name] = value

        logger.debug("Successfully updated %s[%s] = %s", icao_hex, column_name, value)
        return True

    except ValueError as ve:
        logger.error("Validation error for %s: %s", icao_hex, str(ve))
        return False
    except Exception as e:
        logger.error(
            "Unexpected error adding to heli_types for %s[%s]: %s",
            icao_hex,
            column_name,
            str(e),
        )
        return False


def remove_from_htypes(icao_hex: str, column_name: str | None = None) -> bool:
    """
    Remove an entry or specific column from the helicopter types dictionary.

    Args:
        icao_hex (str): The ICAO hex code of the aircraft (case-insensitive)
        column_name (str | None): The name of the field to remove. If None, removes entire ICAO entry.
                                Defaults to None.

    Returns:
        bool: True if removal was successful, False if entry/column not found or error occurred

    Example:
        >>> remove_from_htypes('ac9f65', 'type')  # Remove specific column
        True
        >>> remove_from_htypes('ac9f65')  # Remove entire ICAO entry
        True
        >>> remove_from_htypes('invalid', 'type')  # Non-existent ICAO
        False
    """
    try:
        # Validate input
        if not isinstance(icao_hex, str) or not icao_hex.strip():
            raise ValueError("ICAO hex code must be a non-empty string")
        if column_name is not None and (
            not isinstance(column_name, str) or not column_name.strip()
        ):
            raise ValueError("Column name must be a non-empty string if provided")

        # Normalize ICAO hex code
        icao_hex = icao_hex.lower().strip()

        # Check if ICAO exists
        if icao_hex not in heli_types:
            logger.debug("ICAO %s not found in heli_types", icao_hex)
            return False

        if column_name is None:
            # Remove entire ICAO entry
            del heli_types[icao_hex]
            logger.debug("Removed entire entry for ICAO %s", icao_hex)
            return True
        else:
            # Remove specific column
            column_name = column_name.strip()
            if column_name in heli_types[icao_hex]:
                del heli_types[icao_hex][column_name]
                logger.debug("Removed column %s for ICAO %s", column_name, icao_hex)

                # If no columns left, remove entire entry
                if not heli_types[icao_hex]:
                    del heli_types[icao_hex]
                    logger.debug("Removed empty entry for ICAO %s", icao_hex)

                return True
            else:
                logger.debug("Column %s not found for ICAO %s", column_name, icao_hex)
                return False

    except ValueError as ve:
        logger.error("Validation error for %s: %s", icao_hex, str(ve))
        return False
    except Exception as e:
        logger.error(
            "Unexpected error removing from heli_types for %s: %s",
            icao_hex,
            str(e),
        )
        return False


def search_bills(icao_hex: str, column_name: str) -> str | None:
    """
    Search for a specific column value in the helicopter database by ICAO hex code.

    Args:
        icao_hex (str): The ICAO hex code to look up (case-insensitive)
        column_name (str): The column/field name to retrieve (e.g., 'type', 'tail', 'operator')

    Returns:
        str | None:
            - The requested value if found
            - Empty string if ICAO exists but requested field is empty
            - None if ICAO not found or error occurs

    Example:
        >>> search_bills("ac9f65", "type")
        "MD52"
        >>> search_bills("ac9f65", "tail")
        "N12345"
        >>> search_bills("unknown", "type")
        None
    """
    try:
        # Ensure icao_hex is lowercase for consistent lookup
        icao_hex = str(icao_hex).lower()
        logger.debug(
            "Searching bills database - ICAO: %s, Column: %s", icao_hex, column_name
        )

        # Check if ICAO exists in database
        if icao_hex not in heli_types:
            logger.debug("ICAO %s not found in database", icao_hex)
            return None

        # Get the requested field, defaulting to empty string if field exists but is empty
        value = heli_types[icao_hex].get(column_name)

        # Return empty string for null/empty values, otherwise return the value
        return "" if value is None else value

    except Exception as e:
        logger.error(
            "Error searching bills database - ICAO: %s, Column: %s, Error: %s",
            icao_hex,
            column_name,
            str(e),
        )
        return None


def load_helis_from_url(bills_url):
    """
    Load helicopter data from a remote URL into a dictionary.

    Downloads and processes helicopter operator data from a specified URL, saves a local
    copy of the data, and builds a dictionary mapping ICAO hex codes to helicopter details.

    Args:
        bills_url (str): URL pointing to the CSV file containing helicopter operator data

    Returns:
        tuple[dict, float | None]:
            - dict: Mapping of lowercase ICAO hex codes to helicopter details
            - float: Timestamp of when the data was downloaded, or None if download failed

    Raises:
        requests.exceptions.RequestException: If there's an error downloading the data

    Note:
        - Creates backup of existing bills_operators.csv before updating
        - Retries with increasing delay on timeout
        - Saves downloaded data to local CSV file for future use
    """
    helis_dict = {}

    status_code = 0
    sleep_time = 10

    while status_code != 200:
        try:
            bills = requests.get(bills_url, timeout=sleep_time)
            status_code = bills.status_code
        except requests.exceptions.Timeout:
            logger.warning("Connection Timed out for Bills -- sleeping %d", sleep_time)
            sleep(sleep_time)
            sleep_time += 5
        except requests.exceptions.RequestException as e:
            raise

    logger.debug("Request returns Status_Code: %s", bills.status_code)

    if bills.status_code == 200:
        tmp_bills_age = time()
        # Saving Copy for subsequent operations
        # Note: it would be best if we were in the right directory before we tried to write
        with open(
            conf_folder + "/bills_operators_tmp.csv", "w", encoding="UTF-8"
        ) as tmpcsvfile:
            try:
                tmpcsvfile.write(bills.text)
                tmpcsvfile.close()
                if os.path.exists(conf_folder + "/bills_operators.csv"):
                    old_bills_age = check_bills_age()
                else:
                    old_bills_age = 0

                if old_bills_age > 0:
                    os.rename(
                        conf_folder + "/bills_operators.csv",
                        conf_folder
                        + "/bills_operators_"
                        + strftime("%Y%m%d-%H%M%S")
                        + ".csv",
                    )
                os.rename(
                    conf_folder + "/bills_operators_tmp.csv",
                    conf_folder + "/bills_operators.csv",
                )
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
    Load helicopter data from the local bills_operators CSV file.

    Reads the local bills_operators.csv file containing helicopter operator data and
    builds a dictionary mapping ICAO hex codes to helicopter details. Also checks
    the age of the file to warn about outdated data.

    Returns:
        tuple[dict, float]:
            - dict: Mapping of lowercase ICAO hex codes to helicopter details
                   (including type, tail number, and operator information)
            - float: Unix timestamp of when the file was last modified

    Note:
        - Requires bills_operators global variable to be set with valid file path
        - Logs warnings if file is more than 24 hours old
        - All ICAO hex codes are converted to lowercase for consistency

    Example:
        >>> helis_dict, file_age = load_helis_from_file()
        >>> print(helis_dict['ac9f65']['type'])
        'MD52'
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


def check_bills_age() -> float:
    """
    Get the age (modification time) of the bills_operators file.

    Returns:
        float:
            - Unix timestamp of file's last modification time
            - 0.0 if file not found or error occurs

    Note:
        The bills_operators global variable must be properly set before calling this function.
        A return value of 0.0 indicates the file doesn't exist or isn't accessible.

    Example:
        >>> check_bills_age()
        1705987654.123  # File exists, last modified at this timestamp
        >>> check_bills_age()
        0.0  # File not found or error occurred
    """
    try:
        # Get file modification time
        bills_age = os.path.getmtime(bills_operators)

        # Convert timestamp to readable format for logging
        readable_time = datetime.fromtimestamp(bills_age).strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(
            "Bills file last modified at %s (timestamp: %.3f)", readable_time, bills_age
        )

        return bills_age

    except FileNotFoundError:
        logger.warning("Bills operators file not found at: %s", bills_operators)
        return 0.0

    except (PermissionError, OSError) as e:
        logger.error(
            "Error accessing bills operators file at %s: %s", bills_operators, str(e)
        )
        return 0.0


def init_prometheus() -> Counter:
    """
    Initialize Prometheus metrics for monitoring helicopter data collection.

    Initializes global counters for:
    - Received messages (by ICAO and callsign)
    - MongoDB insert operations (by status code)
    - Message sources (by source type)
    - Update operation timing

    Returns:
        Counter: The fcs_rx counter for tracking received messages

    Raises:
        Exception: If there's an error initializing any metric

    Note:
        This function modifies global variables for metric tracking.
        All metrics are prefixed with 'fcs_' (Feed CopterSpotter).
    """
    try:
        # Declare globals to be modified
        global fcs_rx, fcs_mongo_inserts, fcs_sources, fcs_update_heli_time

        # Initialize counters with descriptive labels
        fcs_rx = Counter(
            name="fcs_rx_msgs",
            documentation="Messages received from aircraft",
            labelnames=["icao", "cs", "feeder_id"],
        )

        fcs_mongo_inserts = Counter(
            name="fcs_mongo_inserts",
            documentation="MongoDB insert operations by status code",
            labelnames=["status_code", "feeder_id"],
        )

        fcs_sources = Counter(
            name="fcs_msg_srcs",
            documentation="Message sources by type (ADSB, MLAT, etc)",
            labelnames=["source", "feeder_id"],
        )

        logger.info("Prometheus metrics initialized successfully")
        return fcs_rx

    except Exception as e:
        logger.error("Failed to initialize Prometheus metrics: %s", str(e))
        raise


# Decorate function with metric.
# @update_heli_time.time()
# def process_prometheus(t):
#     """A dummy function that takes some time."""
#     tx.labels("foo", "bar").inc()
#     tx.labels("boo", "baz").inc()
#     sleep(t)


def run_loop(interval, h_types):
    """
    Main processing loop for helicopter data collection and monitoring.

    Continuously runs the helicopter data collection process at specified intervals,
    updating the bills database when needed and periodically dumping status information.

    Args:
        interval (int): Number of seconds to sleep between processing cycles
        h_types (dict): Dictionary containing helicopter type information keyed by ICAO hex

    Note:
        - Checks bills_operators.csv age and updates from URL if older than BILLS_TIMEOUT
        - Dumps helicopter status information once per hour by default
        - Runs indefinitely until interrupted
        - Uses global variables: BILLS_URL, BILLS_TIMEOUT

    Example:
        >>> run_loop(60, heli_types_dict)  # Run with 60-second intervals
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
            h_types, bills_age = load_helis_from_url(BILLS_URL)
            logger.info("Updated bills_operators.csv at: %s", ctime(bills_age))
        else:
            logger.debug(
                "bills_operators.csv less than timeout value old - last updated at: %s",
                ctime(bills_age),
            )

        fcs_update_helidb(interval)
        emit_mongo_connection_stats_if_due()

        # dump 1x per hour
        if dump_clock >= (60 * 60 / interval):
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
        print("{parser.prog} version: {VERSION} from: {CODE_DATE}")
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
            os.path.join(conf_folder, "bills_operators.csv")
        ):
            logger.debug("Conf folder found: %s", conf_folder)
            break
        else:
            conf_folder = "/app/data"

    env_file = os.path.join(conf_folder, ".env")

    bills_operators = os.path.join(conf_folder, "bills_operators.csv")

    config = {
        **dotenv_values(env_file),
        **os.environ,
    }

    MONGO_CONN_LOG_ENABLED = parse_bool_config(
        config.get("MONGO_CONN_LOG_ENABLED"),
        DEFAULT_MONGO_CONN_LOG_ENABLED,
    )
    MONGO_CONN_LOG_INTERVAL_SECS = parse_positive_int_config(
        config.get("MONGO_CONN_LOG_INTERVAL_SECS"),
        DEFAULT_MONGO_CONN_LOG_INTERVAL_SECS,
        "MONGO_CONN_LOG_INTERVAL_SECS",
    )

    # somewhat redundant here but logging is bootstrapped before reading config
    if "DEBUG" in config and config["DEBUG"] == "True":
        #        ch=logging.StreamHandler()
        #        ch.setLevel(logging.DEBUG)
        #        logger.addHandler(ch)

        logger.setLevel(logging.DEBUG)
        logger.debug("Debug Mode Enabled")

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM (%s) -- Exiting...", signum)
        close_mongo_client()
        raise SystemExit(0)

    atexit.register(close_mongo_client)

    # Should be pulling these from env

    # If we find the API-Key - use that. Otherwise try login/password method.
    if (
        "API-KEY" in config
        and config["API-KEY"] != "BigLongRandomStringOfLettersAndNumbers"
    ):
        logger.debug("Mongo API Key found - using https api ")
        MONGO_CONN_TRACKING_ACTIVE = False
        MONGO_API_KEY = config["API-KEY"]
        mongo_insert = mongo_https_insert
        if "MONGO_URL" in config:
            MONGO_URL = config["MONGO_URL"]

        elif args.mongourl:
            MONGO_URL = args.mongourl

        else:
            MONGO_URL = None
            logger.error("API-Key found but No Mongo Endpoint URL specified - Exiting")
            sys.exit()

    # 20241226 - why is this section here? dhb
    # elif (
    #     "API_KEY" in config
    #     and config["API_KEY"] != "BigLongRandomStringOfLettersAndNumbers"
    # ):
    #     logger.debug("Mongo API Key found - using https api ")
    #     MONGO_API_KEY = config["API_KEY"]
    #     mongo_insert = mongo_https_insert
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
        MONGO_CONN_TRACKING_ACTIVE = True
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

    if MONGO_CONN_TRACKING_ACTIVE:
        if MONGO_CONN_LOG_ENABLED:
            logger.info(
                "Mongo connection logging enabled at %d second interval(s)",
                MONGO_CONN_LOG_INTERVAL_SECS,
            )
        else:
            logger.info("Mongo connection logging disabled")

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

    # Logging should be running by now
    logger.info(f"Starting {parser.prog} version: {VERSION} from: {CODE_DATE}")
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if server and port:
        AIRCRAFT_URL = f"http://{server}:{port}/data/aircraft.json"

        validation = validators.url(AIRCRAFT_URL)

        if validation:
            logger.info("Using AIRCRAFT_URL: <%s>", AIRCRAFT_URL)
        else:
            logger.warning(
                "AIRCRAFT_URL is invalid - setting to None - check .env for errors: <%s>",
                AIRCRAFT_URL,
            )
            AIRCRAFT_URL = None

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
        heli_types, bills_age = load_helis_from_url(BILLS_URL)
        logger.info("Loaded bills_operators from URL: %s ", BILLS_URL)

    elif bills_age > 0:
        logger.debug("Loading bills_operators from file: %s ", bills_operators)
        heli_types, bills_age = load_helis_from_file()
        logger.info("Loaded bills_operators from file: %s ", bills_operators)

    else:
        logger.error("Bills Operators file not found at %s -- exiting", bills_operators)
        raise FileNotFoundError

    logger.info("Loaded %s helis from Bills", str(len(heli_types)))

    if args.once:
        fcs_update_helidb(99999)
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
            signal.signal(signal.SIGTERM, handle_sigterm)
            init_prometheus()
            start_http_server(PROM_PORT)
            run_loop(args.interval, heli_types)

    else:
        try:
            logger.debug("Starting main processing loop")
            signal.signal(signal.SIGTERM, handle_sigterm)
            init_prometheus()
            start_http_server(PROM_PORT)
            run_loop(args.interval, heli_types)

        except KeyboardInterrupt:
            logger.warning("Received Keyboard Interrupt -- Exiting...")
            sys.exit()
