# Ricoh Theta tools
### Version 1.2.0

Linux client and Python class to remote-control a Ricoh Theta camera from the command line

Also includes scripts I made for my own purpose, such as a script to remotely trigger shots at regular intervals to create 360° timelapse videos.

**THIS CODE WAS NOT MADE WITH AI!**

## Why?

I'm a big fan of 360° photography, and particularly timelapse and night-time photography.

One of my latest projects with my Ricoh Theta X camera is to set it up outside overnight to capture northern lights in the winter. The problem is, Theta cameras don't offer interval shooting in combination with long exposure. So triggering the shots has to be done with a Bluetooth intervalometer (which works perfectly fine) or remotely through wifi.

The spot where I leave the camera overnight has wifi: I can leave it there and connect to it from the house with the Ricoh Theta cellphone app. Also, it's convenient to download files remotely from the camera without moving it, while it's taking shots. 

But to trigger the shot programmatically, I needed to talk to it from my Linux server. And I really wanted to download files directly to my machine without using the cellphone app.

Fortunately, Ricoh has published the entire web API to talk to Theta cameras here:

[https://docs-theta-api.ricoh360.com/web-api/index.html](https://docs-theta-api.ricoh360.com/web-api/index.html)

Initially, I cobbled together a few shell scripts to setup the camera and trigger the shots with curl. But the wifi connection is a bit flaky, and every once in a while, it would disconnect and the interval shooting script would miss shots or stop completely halfway through the night.

I tried to adapt it to reconnect as quickly as possible, and reboot the camera in case of some other problems. But shell scripting isn't terribly flexible for proper error handling.

Also, I wanted to keep the HTTP session open to avoid reconnecting to the camera each time I needed to send it a command. The camera is more stable and the commands are faster with long-lived HTTP sessions. Unfortunately, sessions are not possible in a simple shell script.

So I scrapped the shell scripts and made a proper Python class to handle communication with Theta cameras properly, and a general-purpose command-line utility to expose the class' power, settings, shot-taking, capture, preview and file operations. I also recoded the interval shooting script in Python to use the class and handle errors gracefully.

This is what's in this repo.

The class does not implement the entire Ricoh Theta web API, but it's complete enough to handle the vast majority of what a Theta camera can do. It's certainly complete enough for my purpose 🙂

## Usage

### Camera setup

- The camera must be connected to the wifi access point in client mode
- The wifi client-mode password must be set

### Setting the wifi client-mode password

This may be done with the [Ricoh360 app](https://play.google.com/store/apps/details?id=com.ricoh360.mobile).

If you'd rather not run that app however, connect your computer to the camera in AP mode (what Ricoh calls "direct mode") and use the `password` command in `theta_do.py`, e.g.:

```shell
$ ./theta_do.py password abc123
{
  "name": "camera.setOptions",
  "state": "done"
}
```

Once the password is set, you never need to do it again and you can leave the wifi in client mode in the camera's settings.

### Creating the credentials configuration file

The camera and its client-mode credentials must be declared in `~/.ricoh_theta_creds.json`. If you have several Ricoh Theta cameras, they may all be declared in that file.

Create the file manually with the following format:

```json
{
  "name1": {
    "addr": "address1",
    "username": "THETAserial#1",
    "password": "password1"
  },
  "name2": {
    "addr": "address2",
    "username": "THETAserial#2",
    "password": "password2"
  },
  ...
}
```

### General-purpose utility

The general-purpose command-line utility is ```theta_do.py```. It expects one command followed by whatever arguments that command may require.

You can list the commands with `theta_do.py -h`:

```shell
$ ./theta_do.py  -h
usage: theta_do.py [-h] [-c CAMERA]
                   {info,state,password,eventlog,powermode,powersaving,reboot,ui,livepreview,fileformat,filter,program,ev,stitching,capturemode,delay,capture,takephoto,storage,list,last,delete,metadata,download,view} ...

positional arguments:
  {info,state,password,eventlog,powermode,powersaving,reboot,ui,livepreview,fileformat,filter,program,ev,stitching,capturemode,delay,capture,takephoto,storage,list,last,delete,metadata,download,view}
    info                Query camera information
    state               Query the state of the camera
    password            Set the client-mode password when connected in AP mode
    eventlog            Retrieve the event log
    powermode           Get or set the power mode
    powersaving         Get or set power saving
    reboot              Reboot the camera
    ui                  Lock or unlock the UI
    livepreview         View the live preview MJPEG stream
    fileformat          list, get or set the file format
    filter              Get or set the filter
    program             Get or set the exposure program
    ev                  Get or set the exposure compensation
    stitching           Get or set the stitching mode
    capturemode         Get or set the capture mode
    delay               Get or set the exposure delay
    capture             Start or stop video capture
    takephoto           Take a photo
    storage             Get storage information
    list                List files
    last                Get the last file created
    delete              delete one or more files
    metadata            Get a file's metadata
    download            download one or more files
    view                View a file URL from the camera or a local file

options:
  -h, --help            show this help message and exit
  -c, --camera CAMERA   Name of the camera to use, declared in
                        ~/.ricoh_theta_creds.json. If omitted, use name saved
                        in ~/.current_ricoh_theta.json
```

To view the arguments required by a particular command, do ```theta_do.py <command> -h```. E.g.:

```shell
./theta_do.py list -h
usage: theta_do.py list [-h] [-f {all,image,video}]

options:
  -h, --help            show this help message and exit
  -f, --filetype {all,image,video}
                        Type of files to list. Default: all
```

The first time the utility is run, it needs to know the name of the theta camera it should use, as declared in `~/.ricoh_theta_creds.json`. Pass it the name using the `-c` argument, e.g.:

```shell
$ ./theta_do.py -c name1 storage
Total:     230.86 G
Remaining: 199.24 G
```

But you don't need to use `-c` afterward: the utility saves the name of the camera for later user.

If you have more than one camera and you want to change camera, use `-c` again.



### External helper programs

#### Live preview video

When using the ```livepreview``` command, the utility receives the live preview MJPEG stream from the camera and pipes it to an external player's standard input.

By default, the viewer spawned by the command is [mpv](https://mpv.io/) with the [mpv360](https://github.com/kasper93/mpv360) extension installed.

The mpv player is available as a pre-built package in most Linux distribution. The mpv360 extension is available here:

[https://github.com/kasper93/mpv360](https://github.com/kasper93/mpv360)

#### viewing images or playing videos

The ```view``` command may be used to view an image or play a video locally, or from the camera (i.e. the command downloads the file from the camera then opens it).

##### Default image viewer

By default, the viewer spawned by the command to display panoramic images is [SphereView](https://github.com/dynobo/sphereview) installed as a [Flatpak package](https://flathub.org/en/apps/io.github.dynobo.sphereview).

You can install the pre-built Flatpak package by doing `flatpak install io.github.dynobo.sphereview` as root.

##### Default video player

By default, the player spawned by the command to play panoramic videos is [VLC](https://www.videolan.org/).

VLC is available as a pre-built package in most Linux distributions.
