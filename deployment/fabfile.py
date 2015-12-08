import os
import sys
import tarfile
from fabric.api import env, cd, run, put, settings, prefix, task, local, get
from fabric.network import key_filenames

env.roledefs = {
    'integration':  ['root@192.168.5.138:33022'],
    'recette':      ['root@192.168.5.138:33022'],
    'production':   ['root@192.168.5.138:33022'],
}

env.app_name = "pdf-print-service"
env.app_user = "pdf"
env.app_group = "pdf"
env.app_fqdn = "pdf-print-service.akema.fr"
env.app_dir = "/usr/local/%(app_name)s" % env
env.log_dir = "%(app_dir)s/log" % env
env.django_app_dir = "%(app_dir)s/pdf_print_service" % env
env.static_dir = "%(app_dir)s/www/static" % env
env.frontend_dir = "%(app_dir)s/frontend/" % env
env.fab_dir = os.path.dirname(os.path.abspath(__file__))
env.local_dir = os.path.normpath(os.path.join(env.fab_dir, ".."))
env.rsync_filter = os.path.join(env.fab_dir, "rsync_filter")
env.app_folder_list = ('deployment', 'pdf_print_service')
env.app_other_files_list = ('LICENSE', 'README.md', 'requirements.txt')

sys.path.append(env.fab_dir)
from fabric_common import *

# try:
#     import local_settings
#
#     if hasattr(local_settings, 'key_filename'):
#         env.key_filename = local_settings.key_filename
# except ImportError:
#     print >> sys.stderr, "Can't find local_settings.py ; No roles definitions"
#


@task
def test():
    print(env.host, env.port)


@task
def get_lasttag():
    import subprocess
    label = subprocess.check_output(["git", "describe"]).strip()
    stats = subprocess.check_output(['git', 'diff', '--shortstat'])
    dirty = len(stats) > 0 and stats[-1]
    return '%s%s' % (label, dirty and "-dirty" or "")

@task
def make_archive():
    cur_dir = os.curdir
    try:
        os.chdir(env.local_dir)
        version = get_lasttag()
        os.system("rm -f build-%s-*.tar.gz" % env.app_name)
        archive_name = 'build-%s-%s.tar.gz' % (env.app_name, version)
        with tarfile.open(archive_name, "w:gz") as tar:
            def exclude(tarinfo):
                name = tarinfo.name.lower()
                if name.endswith('.pyc') or name.endswith('.pyo'):
                    return None
                if name in ['log', '__pycache__'] and tarinfo.isdir():
                    return None
                if name in ['db.sqlite3', ] and tarinfo.isfile():
                    return None
                return tarinfo

            # tar.add('deployment', filter=exclude)
            tar.add('pdf_print_service', filter=exclude)
            tar.add('deployment/requirements', filter=exclude)
            for fname in env.app_other_files_list:
                tar.add(fname)
        print("Archive created: %s" % archive_name)
        return archive_name
    finally:
        os.chdir(cur_dir)

import fabric_common
fabric_common.make_archive = make_archive
