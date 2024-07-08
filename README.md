# CopterFeeder

## Table of Contents

-   [Prerequisites](#prerequisites)
-   [Running with Docker](#running-with-docker)
    -   [Installation](#installation)
        -   [Option 1: Using ADSB.IM Image](#option-1-using-adsbim-image)
        -   [Option 2: Manual Setup with Ubuntu](#option-2-manual-setup-with-adsbim-and-ubuntu)
    -   [Configuration and Running](#configuration-and-running)
    -   [Updating Copterfeeder](#updating-copterfeeder)
-   [Running without Docker](#running-without-docker)

## Prerequisites

-   A Raspberry Pi or another host with Ubuntu or a similar Linux distribution
-   A supported SDR, see the ADSB.im [supported list](https://www.adsb.im/supported#sdrs)

<br>

# Running with Docker

## Installation

### Option 1: Using ADSB.IM Image

1. Download and install the [ADSB.im](https://adsb.im) image on your device
2. Follow their [how-to guide](https://www.adsb.im/howto) for hardware setup and image loading
3. Proceed to the [Configuration and Running](#configuration-and-running) section

### Option 2: Manual Setup with ADSB.im and Ubuntu

📌 **Note:** If you already have Git and Docker installed, skip to step 6: [Install ADSB.im](#install-adsbim)

1. Update your system:

    ```shell
    sudo apt update
    sudo apt upgrade
    ```

2. Install Docker and docker-compose:

    ```shell
    sudo apt install docker.io docker-compose
    ```

3. To run Docker commands without sudo, add your user to the Docker group:

    ```shell
    sudo usermod -aG docker $USERNAME
    ```

    📝 **Note:** fill in your username like `$JOHNDOE`

4. Apply the new group membership:

    ```shell
    newgrp docker
    ```

5. Install Git

    ```shell
    sudo apt install git
    ```

6. #### Install ADSB.im:

    ```shell
    curl https://raw.githubusercontent.com/dirkhh/adsb-feeder-image/main/src/tools/app-install.sh | sudo bash
    ```

## Configuration and Running

1. Clone the repository:

    ```shell
    git clone https://github.com/LoganSound/CopterFeeder.git
    cd CopterFeeder
    ```

2. Set up the environment file:

    ```shell
    cp .env.example .env
    nano .env
    ```

    📝 Fill in the required values provided by the dev team and your feeder name

    💡 **Nano tips:** Save (Ctrl+O, Enter) | Exit (Ctrl+X)

3. Build and run the Docker container:

    ```shell
    docker-compose build
    docker-compose up -d
    ```

    📝 **Note:** If you already had docker installed through another method, newer versions use `docker compose` instead of `docker-compose` and you may need to modify these scripts

4. (Optional) View logs:
    ```shell
    docker compose logs -f
    ```

## Updating CopterFeeder

1. Navigate to the project folder and pull the latest

    ```shell
    cd ./CopterFeeder
    git pull
    ```

2. Build and restart the Docker container:

    ```shell
    docker-compose build
    docker-compose down
    docker-compose up -d
    ```

    **Note:** If you already had docker installed through another method, newer versions use `docker compose` instead of `docker-compose` and you may need to modify these scripts

    <br>
    <br>

# Running without Docker

Update your package list:

```Shell
sudo apt update
```

If your system hasn't had its Operating system updated in a while, you may need to run:

```Shell
sudo apt upgrade
```

If you are not using the adsb.im, to use this script with docker you will first need to install Docker and docker compose on your machine. If you need help for this step, search the web for your version of Linux, etc. It could be as simple as:

```Shell
sudo apt install docker.io docker-compose
```

There may be other setup steps required - such as adding yourself to the docker group to give yourself privileges to run docker without needed root access. Again, out of scope for this readme.md file. Depending on which version of docker you have installed, it may already include "compose" -- as such, you may not need to install docker-compose. If this is the case, just use "docker compose" instead of "docker-compose"

The following is required if you don't have pip3 installed (eg: FR24 feeder images ) - Note that in later OS releases, it is not recommended to use "sudo pip3" to install libraries, rather either using the OS tools like apt to install python-XYZ or using a "venv" is preferred. See: https://packaging.python.org/en/latest/tutorials/installing-packages/ for more detailed information.

```Shell
sudo apt-get install python3-pip
```

Get the CopterFeeder script using git:

```Shell
sudo apt-get install git
git clone https://github.com/LoganSound/CopterFeeder.git
```

move into the project folder:

```Shell
cd CopterFeeder/
```

And then (optionally) download the latest helicopter database. This functionality has been included in the main feeder script so is now an optional step.

```Shell
wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "bills_operators.csv"
```

OR (preferred, but still optional) use the incluided "get_bills.py" script to pull the csv file.

```Shell
./get_bills.py
```

Run pip3 to install requirements

```Shell
python3 -m pip3 --user install -r requirements.txt
```

Copy example_env_file to .env ( this should only have to be done for the first install!!!)

```Shell
cp  example_dot_env .env
```

Add your credentials or API-key, and Feeder-ID type to the .env file

```Shell
nano .env
```

Change the permissions on the .env file so that only you read Read/Write the file:

```Shell
chmod go-rwx .env
```

Credentials can also be specified using command line options (see below). Command line options
take precedence over environtment settings. Note that Userid/Password specified on the commandline
will be able to be seen by others using "ps -ef"

Make the main script executable

```Shell
chmod +x feed_copterspotter.py
```

The script needs to be told how to get to the "aircraft.json" on your ADS-B Feeder. It can do this either
by reading local files using the "-r" option or by making a request over the net to small webserver packaged
with the feeder software (dump1090) which is typically lighthttp or similar. Because there are different
directories and urls for this different versions of software, the best way to do this in your setup may
take a bit of trial and error. If you are running the script on the system you use as a ADS-B feeder,
you might want to start with the "-r" option, which will scan several different directories under /run.
If you're on a different machine, you'll want to use the server (-s) and port (-p) options. Note: if you use
the -r option, -s and -p options will be ignored.

The script is intended to be run as a daemon (-d option):

```Shell

./feed_copterspotter.py -d -r

```

Or run on the command line, so that you can watch debugging output (-D option):

```Shell

./feed_copterspotter.py -D -r

```

If you want to run from Crontab, use the -o (one shot) option.

#type:

```Shell
crontab -e
```

And add the following lines (these file paths need to match wherever you installed to, below is example for /home/pi/CopterFeeder):

```Code



Note: Examples below assume the script is installed in "/home/pi/"  - this is not a
requirement and certainly not a recommendation - the script can be installed in a
convenient directory of your choice.

* * * * * python3 /home/pi/CopterFeeder/feed_copterspotter.py -o -r >> copterspotter.log 2>&1
0 0 * * * wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "/home/pi/CopterFeeder/bills_operators.csv"
```

And you're DONE!

You can TEST one iteration by typing:

```Shell

python3 feed_copterspotter.py -o -r



```

When an identifyied helicopter is nearby, in verbose mode (-v switch) or debug mode
(-D switch), the script will output lines something like:

```Code
Helicopter Reported: 1674864903.049228 A139 TRP7 450 600 97.22 38.909385,-76.845398 5107
```

You can optionally log those reports to a file using the -l option, which can be handy if
you're running in daemon mode:

```Code

feed_copterspotter.py -d -l /full/path/to/logfile

```

You can do:

```Code
tail -f /full/path/to/logfile
```

to watch the logging messages in the logfile.

Note: the -D debug mode will be very noisy as it is intended for debugging - you probably want to use -v or -l to just see periodic reports.

If you consistently see "None" or "Null" we may need to tweak your variables

Help is available with the -h or --help option:

```Code
./feed_copterspotter.py --help

usage: feed_copterspotter.py [-h] [-V] [-v] [-D] [-d] [-o] [-l LOG] [-w] [-i INTERVAL] [-s SERVER] [-p PORT]
                             [-u MONGOUSER] [-P MONGOPW] [-f FEEDERID] [-r]

Helicopters of DC data loader

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         Print version and exit
  -v, --verbose         Emit Verbose message stream
  -D, --debug           Emit Debug messages
  -d, --daemon          Run as a daemon
  -o, --once            Run once and exit
  -l LOG, --log LOG     File for logging reported rotorcraft
  -w, --web             Download / Update Bills Operators from Web on startup (defaults to reading local file)
  -i INTERVAL, --interval INTERVAL
                        Interval between cycles in seconds
  -s SERVER, --server SERVER
                        dump1090 server hostname (default localhost)
  -p PORT, --port PORT  alt-http port on dump1090 server (default 8080)
  -u MONGOUSER, --mongouser MONGOUSER
                        MONGO DB User
  -P MONGOPW, --mongopw MONGOPW
                        Mongo DB Password
  -f FEEDERID, --feederid FEEDERID
                        Feeder ID
  -r, --readlocalfiles  Check for aircraft.json files under /run/...
```