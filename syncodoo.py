#!/usr/bin/env python3
from configparser import ConfigParser
import paramiko
import os
import stat
from colorama import init, Fore

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
LOG_STYLES = {
        'error': { 'prestyle': Fore.RED, 'style': Fore.WHITE },
        'ok': { 'prestyle': Fore.GREEN, 'style': Fore.WHITE }
    }
COLOR_MARK = Fore.GREEN
COLOR_TEXT = Fore.WHITE
COLOR_REMARK = Fore.LIGHTRED_EX
COLOR_INFO = Fore.YELLOW
COLOR_ERROR = Fore.RED
COLOR_QUESTION = Fore.YELLOW
SERVERS_PREFIX = "ssh_"
OPTIONS_PREFIX = "_"
ODOO_PREFIX = '_odoo_'
SERVER_PATH_PREFIX = "_path"
BORDER = "*" * 30
IGNORE = ['__pycache__']

class SyncOdoo:

    OPERATIONS = {
        1: "Upload module",
        2: "Download module",
        3: "Create module",
        4: "Restart Odoo",
        5: "Open module",
        6: "Force module update"
    }

    def __init__(self, server):
        self.local_path = ""
        paths = SyncOdoo.config(section="paths")
        if "options" in server and "path" in server["options"]:
            self.remote_path = server["options"]["path"]
        else:
            self.remote_path = paths["remote"]
        self.odoo = server["odoo"] 
        self.local_path = paths["local"]
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(**server["ssh"])
        self.sftp = self.ssh.open_sftp()

    def get_odoo(self, server):
        ODOO_PREFIX = "odoo_"
        if server and server["options"]:
            options = server["options"].items()
            odoo = {k.replace(ODOO_PREFIX, ""): v for k,v in options if k.startswith(ODOO_PREFIX)}
            return odoo
        return {}

    def config(filename=CONFIG_FILE, section="paths"):
        parser = ConfigParser()
        parser.read(filename)
        config = {}
        if parser.has_section(section):
            config = {p[0]: p[1] for p in parser.items(section)}

        return config
    
    def get_servers(filename=CONFIG_FILE):
        parser = ConfigParser()
        parser.read(filename)
        sections = parser.sections()
        servers = filter(lambda section: section.startswith(SERVERS_PREFIX), sections)
        data = {}
        for server in servers:
            ssh = {k: v for k,v in parser.items(server) if not k.startswith(OPTIONS_PREFIX) and not k.startswith(ODOO_PREFIX)}
            options = {k.replace(OPTIONS_PREFIX,'', 1): v for k,v in parser.items(server) if k.startswith(OPTIONS_PREFIX) and not k.startswith(ODOO_PREFIX)}
            odoo = {k.replace(ODOO_PREFIX,'', 1): v for k,v in parser.items(server) if k.startswith(ODOO_PREFIX)}
            server = server.replace(SERVERS_PREFIX,"")
            data[server] = {
                "ssh": ssh,
                "options": options,
                "odoo": odoo
                }
        return data
    
    def get_ssh_data(filename=CONFIG_FILE, server="dev"):
        data = SyncOdoo.config(section=f"ssh_{server}")
        default_path = SyncOdoo.config(section="paths")
        path = data.pop(SERVER_PATH_PREFIX, default_path["remote"])
        return [data, path]

    def close(self):
        if self.ssh is not None:
            if self.sftp is not None:
                self.sftp.close()
                self.sftp = None
            self.ssh.close()
            self.ssh = None
    
    def menu(options, option_def, title, question="Option"):
        # SyncOdoo.clear()
        while True:
            print(f"\n\n{COLOR_MARK}{BORDER}\n\t {title}\n{BORDER}")
            for k, v in options.items():
                print(f"[{COLOR_MARK}{k}{COLOR_TEXT}] {v}")
            try:
                option = input(f"\n{COLOR_INFO}{question} ({COLOR_REMARK}0 to exit{COLOR_INFO}): ")
                if option == "":
                    option = option_def
                option = int(option)
                if option == 0:
                    print(COLOR_ERROR+"<<< Close >>>")
                    os._exit(0)
                if option in options:
                    return [option, options[option]]
            except:
                pass
            print(COLOR_ERROR+"<<< Invalid option >>>")

    
    def get_modules(self, on="local"):
        if on == "local":
            modules = os.listdir(self.local_path)
        else:  
            modules = self.sftp.listdir(self.remote_path)
        
        modules.sort()
        return SyncOdoo.list_to_dic(modules)  

    def get_module_dir(self, module, on="remote"):
        if on == "remote":
            module_dir = f"{self.remote_path}/{module}"
        else: 
            module_dir = os.path.join(self.local_path, module)
        return module_dir

    def remote_exec_command(self, command):
        inp, outp, error = self.ssh.exec_command(command)
        SyncOdoo.log('Output', outp.read())
        SyncOdoo.log('Errors', error, 'error')
        return {"input": inp, "output": outp, "error": error}

    def remote_delete_module(self, path):
        self.remote_exec_command(f"rm -r {path}")
    
    def local_delete_module(self, path):
        os.system(f"rm -r {path}")

    def clear():
        os.system("clear")
    
    def remote_set_all_permisions(self, path):
        self.remote_exec_command(f"chmod -R 777 {path}")
    
    def log(pre, text, type='ok', end="\n"):
        style = LOG_STYLES[type]
        print(f"{style['prestyle']}{pre}...{style['style']}{text}", end=end)
    
    def remote_create_module(self, module):
        SyncOdoo.log('Creating module', module)
        self.remote_exec_command(f"odoo scaffold {module} {self.remote_path}")

    def remote_upload(self, origen, dest):
        for item in os.listdir(origen):
            from_path_item = os.path.join(origen, item)
            to_path_item = f"{dest}/{item}"
            if item not in IGNORE:
                if os.path.isfile(from_path_item):
                    try:
                        SyncOdoo.log(pre='Uploading', text=from_path_item, end=" ...")
                        self.sftp.put(from_path_item, to_path_item)
                        SyncOdoo.log("Ok","")
                    except Exception as error:
                        SyncOdoo.log('Upload error', error, 'error')
                else: 
                    self.remote_mkdir(to_path_item)
                    self.remote_upload(from_path_item, to_path_item)

    def local_download(self, from_path, to_path): 
        for item in self.sftp.listdir_attr(from_path):
            from_path_item = f"{from_path}/{item.filename}"
            to_path_item = os.path.join(to_path, item.filename)
            if item.filename not in IGNORE:
                if stat.S_ISDIR(item.st_mode):
                    self.local_mkdir(to_path_item)
                    self.local_download(from_path_item, to_path_item)
                else:
                    try:
                        SyncOdoo.log(pre='Downloading', text=to_path_item, end=" ...")
                        self.sftp.get(from_path_item, to_path_item)
                        SyncOdoo.log("Ok","")
                    except Exception as error:
                        SyncOdoo.log('Download error', error, 'error')
    
    def question_yes_no(question, default="n", cancel=False, options=['y','n']):
        if cancel:
            options.append('c')
        options_text = "/".join(options)

        yes_no = default 
        while True:
            yes_no = input(f"{COLOR_QUESTION}{question} ({COLOR_REMARK}{options_text}{COLOR_QUESTION})[{default}]: ")
            if yes_no == "":
                yes_no = default 
            if yes_no in options:
                if yes_no == "c":
                    SyncOdoo.log("Close","","error")
                    os._exit(0)
                break
        return yes_no

    def restart_odoo(self, question=True):
        yes_no = "y"
        if question:
            yes_no = SyncOdoo.question_yes_no("¿Restart odoo?")

        if yes_no == "y":
            SyncOdoo.log("Restarting odoo","")
            self.remote_exec_command("service odoo restart")
    def force_update(self, to_path):
        to_path = to_path.split("/")
        module = to_path[-1]
        self.remote_exec_command("service odoo stop")
        self.remote_exec_command(f"{ self.odoo['cmd'] } -c {self.odoo['conf']} -d {self.odoo['bd']} -u {module} &&")

    
    def upload(self, from_path, to_path, force_update=False):
        self.remote_delete_module(to_path)
        self.remote_mkdir(to_path)
        self.remote_upload(from_path, to_path)
        self.remote_set_all_permisions(to_path)
        if not force_update:
            self.restart_odoo()
        else:
            self.force_update(to_path)
    
    def download(self, from_path, to_path):
        self.local_delete_module(to_path)
        self.local_mkdir(to_path)
        self.local_download(from_path, to_path)
        SyncOdoo.open_vc(to_path, False)
    
    def open_vc(path, auto=True):
        cmd = f"code {path}"
        if auto:
            os.system(cmd)
        else: 
            yes_no = SyncOdoo.question_yes_no("¿Open on VS Code?")
            if yes_no == "y":
                os.system(cmd)
    
    def new_module(self):
        module = ""
        while True:
            module = input("New module name: ")
            if module != "":
                yes_no = SyncOdoo.question_yes_no(f"Model name [{module}], ¿It`s ok?")
                if(yes_no == "y"):
                    break
        self.remote_create_module(module)

        from_path = self.get_module_dir(module)
        to_path = self.get_module_dir(module,'local')

        self.local_mkdir(to_path)
        self.local_download(from_path, to_path)
        SyncOdoo.open_vc(to_path, False)

    def remote_mkdir(self, path):
        try:
            self.sftp.mkdir(path)
            SyncOdoo.log("Folder created", path)
        except IOError as error:
            SyncOdoo.log('Error', error, 'error')
    
    def local_mkdir(self, path):
        try:
            os.mkdir(path)
            SyncOdoo.log('Folder created', path)
        except Exception as error:
            SyncOdoo.log('Error', error, 'error')

    def keys_to_dic(data):
        keys = list(data.keys())
        return SyncOdoo.list_to_dic(keys) 

    def list_to_dic(data):
        return {i: data[i-1] for i in range(1, len(data)+1)}



if __name__ == '__main__':
    SyncOdoo.clear()
    init(autoreset=True)
    option = SyncOdoo.menu(SyncOdoo.OPERATIONS, 1, "Options")[0]

    if option != 0:
        title = "Upload to" if option == 1 else "Download from"
        servers = SyncOdoo.get_servers()
        server_options = SyncOdoo.keys_to_dic(servers)
        from_to = [1, "dev"] 
        if option != 5:
            from_to = SyncOdoo.menu(server_options, 1, title)
        server = servers[from_to[1]] 
        sync = SyncOdoo(server)

        if option in  [1, 2, 6]:
            cfg = {
                1: {'from': 'local', 'to': 'remote', 'title': 'Module to upload', 'fn': sync.upload},
                2: {'from': 'remote', 'to': 'local', 'title': 'Module to download', 'fn': sync.download},
                6: {'from': 'local', 'to': 'remote', 'title': 'Module to upload', 'fn': sync.upload},
            }[option]
            modules = sync.get_modules(cfg['from'])
            module = SyncOdoo.menu(modules, 1, cfg['title'])

            from_path = sync.get_module_dir(module[1], cfg['from'])
            to_path = sync.get_module_dir(module[1], cfg['to'])
            if option == 6:
                cfg['fn'](from_path, to_path, True)
            else:
                cfg['fn'](from_path, to_path)
        elif option == 3:
            sync.new_module() 
        elif option == 4:
            sync.restart_odoo()
        elif option == 5:
            modules = sync.get_modules("local")
            module = SyncOdoo.menu(modules, 1, "Open module")

            path = sync.get_module_dir(module[1], "local")
            SyncOdoo.open_vc(path)

        sync.close()
