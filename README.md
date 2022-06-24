

## CONFIGURATION
Is necesary create a __config.ini__ file, with this structure:

```
    [paths]
    local = /home/myLocal/modulesRootFolder
    ; "remote" is default option when *_path* in [ssh_serverX] is not asigned
    remote /myRemote/modulesRootFolder

    [ssh_serverA]
    hostname = myserverip.com
    username = myusername
    password = mypass
    look_for_keys = True
    ; optional parameter
    _path = /remoteFolder/fromThisServer 
```

