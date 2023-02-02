
Start by running

```Shell
sudo apt-get update
```

The following is required if you don't have pip3 installed (eg: FR24 feeder images )


```Shell
sudo apt-get install python3-pip
```

Get the script using git:

```Shell
sudo apt-get install git
git clone https://github.com/LoganSound/CopterFeeder.git
```

move into the project folder:

```Shell 
cd CopterFeeder/
``` 
And then download the latest helicopter database:

```Shell 
wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "bills_operators.csv"
``` 

Run pip3 to install requirements 
```Shell
pip3 install -r requirements.txt 
```

Copy example_env_file to .env
```Shell
cp  example_dot_env .env
```

Add your credentials and feeder type to the .env file
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

Note: Examples below assume the script is installed in "/home/pi/"  - this is not a
requirement and certainly not a recommendation - the script can be installed in a
convenient directory of your choice. 


The script is intended to be run as a daemon: 

```Shell

/home/pi/feed_copterspotter.py -d -r

```

Or run on the command line, so that you can watch debugging output:

```Shell

/home/pi/feed_copterspotter.py -D -r

```

If you want to run from Crontab, use the -o (one shot) option 

#type:
```Shell
crontab -e
```

And add the following lines (these file paths need to match wherever you installed to, below is example for /home/pi/CopterFeeder):

```Code
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

/home/pi/feed_copterspotter.py -d -l /full/path/to/logfile

```



If you consistently see "None" or "Null" we may need to tweak your variables


Help is available with the -h or --help option: 


```Code
./feed_copterspotter.py --help
usage: feed_copterspotter.py [-h] [-V] [-v] [-D] [-d] [-o] [-l LOG] [-i INTERVAL] [-s SERVER] [-p PORT] [-u MONGOUSER]
                             [-P MONGOPW] [-f FEEDERID] [-r]

Helicopters of DC data loader

options:
  -h, --help            show this help message and exit
  -V, --version         Print version and exit
  -v, --verbose         Emit Verbose message stream
  -D, --debug           Emit Debug messages
  -d, --daemon          Run as a daemon
  -o, --once            Run once and exit
  -l LOG, --log LOG     File for logging reported rotorcraft
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
 
