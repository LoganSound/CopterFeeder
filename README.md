
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
git clone https://github.com/LoganSound/CopterFeeder.git
```

or using curl:

```Shell
curl -LJO https://raw.githubusercontent.com/LoganSound/CopterFeeder/main/feed_copterspotter.py
curl -LJO https://raw.githubusercontent.com/LoganSound/CopterFeeder/main/requirements.txt
```

And then the helicopter database:

```Shell 
wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "/home/pi/bills_operators.csv"
``` 

Run pip3 to install requirements 
```Shell
pip3 install -r requirements.txt 
```

Copy example_env_file to .env
```Shell
cp  example_env_file .env
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

/home/pi/feed_copterspotter.py -d

```

Or run on the command line, so that you can watch debugging output:

```Shell

/home/pi/feed_copterspotter.py -D

```

If you want to run from Crontab, use the -o (one shot) option 

#type:
```Shell
crontab -e
```

And add the following lines:

```Code
* * * * * python3 /home/pi/feed_copterspotter.py -o >> copterspotter.log 2>&1
0 0 * * * wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "/home/pi/bills_operators.csv"
```

And you're DONE!


You can TEST one iteration by typing:

```Shell
python3 feed_copterspotter.py -o 
``` 

When an identifyied helicopter is nearby, in verbose mode (-v switch) or debug mode
(-D switch), the script will output lines something like:

```Code
Helicopter Reported: 1674864903.049228 A139 TRP7 450 600 97.22 38.909385,-76.845398 5107
```

If you consistently see "None" or "Null" we may need to tweak your variables


Help is available with the -h or --help option: 


```Code

./feed_copterspotter.py --help 
usage: feed_copterspotter.py [-h] [-V] [-v] [-D] [-i] [-o] [-s] [-p] [-u] [-P] [-f] [-d]

Helicopters of DC data loader

optional arguments:
  -h, --help       show this help message and exit
  -V, --version    Print version and exit
  -v, --verbose    Emit Verbose message stream
  -D, --debug      Emit Debug messages
  -i, --interval   Interval between cycles in seconds
  -o, --once       Run once and exit
  -s, --server     dump1090 server hostname
  -p, --port       alt-http port on dump1090 server
  -u, --mongouser  MONGO DB User
  -P, --mongopw    Mongo DB Password
  -f, --feederid   Feeder ID
  -d, --daemon     Run as a daemon

```
 
