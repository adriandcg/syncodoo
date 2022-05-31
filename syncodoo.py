#!/usr/bin/env python3
from configparser import ConfigParser
import paramiko
import os
import stat
from colorama import init, Fore

CONFIG_FILE = "config.ini"
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
BORDER = "*" * 30

class SyncOdoo:

    OPERATIONS = {
        1: "Subir módulo",
        2: "Descargar módulo",
        3: "Crear módulo",
        4: "Reiniciar odoo",
        5: "Abrir módulo"
    }

    def __init__(self, server):
        self.local_path = ""
        paths = SyncOdoo.config(section="paths")
        if "options" in server and "path" in server["options"]:
            self.remote_path = server["options"]["path"]
        else:
            self.remote_path = paths["remote"]
        self.local_path = paths["local"]
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(**server["ssh"])
        self.sftp = self.ssh.open_sftp()

    def config(filename=CONFIG_FILE, section="dev"):
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
        servers = filter(lambda section: section.startswith('ssh_'), sections)
        data = {}
        for server in servers:
            ssh = {}
            options = {}
            for option, value in parser.items(server):
                if option.startswith("_"):
                    option = option.replace('_','') 
                    options[option] = value
                else:
                    ssh[option] = value
            server = server.replace("ssh_","")
            data[server] = {"ssh": ssh, "options": options}
        
        # ssh = list(map(lambda s: s.replace('ssh_','') , ssh))
        # return SyncOdoo.list_to_dic(ssh)
        return data
    
    def get_ssh_data(filename=CONFIG_FILE, server="dev"):
        data = SyncOdoo.config(section=f"ssh_{server}")
        default_path = SyncOdoo.config(section="paths")
        path = data.pop("_path", default_path["default_remote"])
        return [data, path]

    def close(self):
        if self.ssh is not None:
            if self.sftp is not None:
                self.sftp.close()
                self.sftp = None
            self.ssh.close()
            self.ssh = None
    
    def menu(options, option_def, title, question="Seleccione una opción"):
        SyncOdoo.clear()
        while True:
            print(f"\n\n{COLOR_MARK}{BORDER}\n\t {title}\n{BORDER}")
            for k, v in options.items():
                print(f"[{COLOR_MARK}{k}{COLOR_TEXT}] {v}")
            try:
                option = input(f"\n{COLOR_INFO}{question} ({COLOR_REMARK}0 para salir{COLOR_INFO}): ")
                if option == "":
                    option = option_def
                option = int(option)
                if option == 0:
                    print(COLOR_ERROR+"<<< Saliendo de la aplicación >>>")
                    os._exit(0)
                if option in options:
                    return [option, options[option]]
            except:
                pass
            print(COLOR_ERROR+"<<< Opción incorrecta >>>")

    
    def get_modules(self, on="local"):
        if on == "local":
            modules = os.listdir(self.local_path)
        else:  
            modules = self.sftp.listdir(self.remote_path)
        
        modules.sort()
        return SyncOdoo.list_to_dic(modules)  

    def get_module_dir(self, module, on="remote"):
        if on == "remote":
            module_dir = "{}/{}".format(self.remote_path, module)
        else: 
            module_dir = os.path.join(self.local_path, module)
        return module_dir

    def remote_exec_command(self, command):
        inp, outp, error = self.ssh.exec_command(command)
        SyncOdoo.log('Salida', outp.read())
        SyncOdoo.log('Errores', error, 'error')
        return {"input": inp, "output": outp, "error": error}

    def remote_delete_module(self, path):
        self.remote_exec_command("rm -r {}".format(path))
    
    def local_delete_module(self, path):
        os.system("rm -r {}".format(path))

    def clear():
        os.system("clear")
    
    def remote_set_all_permisions(self, path):
        self.remote_exec_command('chmod -R 777 {}'.format(path))
    
    def log(pre, text, type='ok', end="\n"):
        style = LOG_STYLES[type]
        print(f"{style['prestyle']}{pre}...{style['style']}{text}", end=end)
    
    def remote_create_module(self, module):
        SyncOdoo.log('Creando modulo', module)
        self.remote_exec_command("odoo scaffold {} {}".format(module, self.remote_path))

    def remote_upload(self, origen, dest):
        for item in os.listdir(origen):
            from_path_item = os.path.join(origen, item)
            to_path_item = "{}/{}".format(dest, item)
            if item != '__pycache__':
                if os.path.isfile(from_path_item):
                    try:
                        SyncOdoo.log(pre='Subiendo', text=from_path_item, end=" ...")
                        self.sftp.put(from_path_item, to_path_item)
                        SyncOdoo.log("Ok","")
                    except Exception as error:
                        SyncOdoo.log('Error al subir', error, 'error')
                else: 
                    self.remote_mkdir(to_path_item)
                    self.remote_upload(from_path_item, to_path_item)

    def local_download(self, from_path, to_path): 
        for item in self.sftp.listdir_attr(from_path):
            from_path_item = "{}/{}".format(from_path, item.filename)
            to_path_item = os.path.join(to_path, item.filename)
            if item.filename != '__pycache__':
                if stat.S_ISDIR(item.st_mode):
                    self.local_mkdir(to_path_item)
                    self.local_download(from_path_item, to_path_item)
                else:
                    try:
                        SyncOdoo.log(pre='Descargando', text=to_path_item, end=" ...")
                        self.sftp.get(from_path_item, to_path_item)
                        SyncOdoo.log("Ok","")
                    except Exception as error:
                        SyncOdoo.log('Error al descargar', error, 'error')
    
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
                    SyncOdoo.log("Saliendo de la aplicación","","error")
                    os._exit(0)
                break
        return yes_no

    def restart_odoo(self, question=True):
        yes_no = "y"
        if question:
            yes_no = SyncOdoo.question_yes_no("¿Desea reiniciar el servicio de odoo?")

        if yes_no == "y":
            SyncOdoo.log("Reiniciando odoo","")
            self.remote_exec_command("service odoo restart")
    
    def upload(self, from_path, to_path):
        self.remote_delete_module(to_path)
        self.remote_mkdir(to_path)
        self.remote_upload(from_path, to_path)
        self.remote_set_all_permisions(to_path)
        self.restart_odoo()
    
    def download(self, from_path, to_path):
        self.local_delete_module(to_path)
        self.local_mkdir(to_path)
        self.local_download(from_path, to_path)
        SyncOdoo.open_vc(to_path, False)
    
    def open_vc(path, auto=True):
        cmd = "code {}".format(path)
        if auto:
            os.system(cmd)
        else: 
            yes_no = SyncOdoo.question_yes_no("¿Desea abrir VS Code?")
            if yes_no == "y":
                os.system(cmd)
    
    def new_module(self):
        module = ""
        while True:
            module = input("Nombre del nuevo módulo: ")
            if module != "":
                yes_no = SyncOdoo.question_yes_no("El módulo se llamará [{}], ¿Es correcto?".format(module))
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
            SyncOdoo.log("Directorio creado", path)
        except IOError as error:
            SyncOdoo.log('Error', error, 'error')
    
    def local_mkdir(self, path):
        try:
            os.mkdir(path)
            SyncOdoo.log('Directorio creado', path)
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
    option = SyncOdoo.menu(SyncOdoo.OPERATIONS, 1, "Acciones")[0]

    if option != 0:
        title = "Subir a" if option == 1 else "Descargar desde"
        # servers = SyncOdoo.keys_to_dic(SyncOdoo.ACCESS_DATA)
        servers = SyncOdoo.get_servers()
        server_options = SyncOdoo.keys_to_dic(servers)
        from_to = [1, "dev"] 
        if option != 5:
            from_to = SyncOdoo.menu(server_options, 1, title)
        server = servers[from_to[1]] 
        sync = SyncOdoo(server)

        if option in  [1, 2]:
            cfg = {
                1: {'from': 'local', 'to': 'remote', 'title': 'Módulo a subir', 'fn': sync.upload},
                2: {'from': 'remote', 'to': 'local', 'title': 'Módulo a descargar', 'fn': sync.download}
            }[option]
            modules = sync.get_modules(cfg['from'])
            module = SyncOdoo.menu(modules, 1, cfg['title'])

            from_path = sync.get_module_dir(module[1], cfg['from'])
            to_path = sync.get_module_dir(module[1], cfg['to'])
            cfg['fn'](from_path, to_path)
        elif option == 3:
            sync.new_module() 
        elif option == 4:
            sync.restart_odoo()
        elif option == 5:
            modules = sync.get_modules("local")
            module = SyncOdoo.menu(modules, 1, "Abrir el módulo")

            path = sync.get_module_dir(module[1], "local")
            SyncOdoo.open_vc(path)

        sync.close()
