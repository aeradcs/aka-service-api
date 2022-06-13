import re
import time

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
import json
from .utils import *

# variables used in a workflow
# (Aka Service context)
variables = {}

# paths to .py and .sh scripts
filename = "/Users/someo/PycharmProjects/aka_service_rest_api/service/api/hpc_scripts/temp.py"
filename_final = "/Users/someo/PycharmProjects/aka_service_rest_api/service/api/hpc_scripts/full_proc_eeg.py"
filename_sh = "/Users/someo/PycharmProjects/aka_service_rest_api/service/api/hpc_scripts/cron.sh"

# paths to .set files which were chosen by user in Aka MiniApp and dates of completing processing these files on hpc
# (Aka MiniApp context)
paths_dates = {}


class VarsView(APIView):

    # get var names list from service context
    def get(self, request, job_id):
        return Response(list(variables.keys()), status=status.HTTP_200_OK)

    # create var in service context and write var logic to python script
    def post(self, request, job_id):
        body = json.loads(request.body)
        if not body['varname'] in variables.keys():
            variables[body['varname']] = body['varvalue']

            # write line of code to .py file based on request info
            write_var(filename, body['varname'], body['varvalue'])

            return Response('OK. Successfully create var.', status=status.HTTP_200_OK)
        else:
            return Response('Var already exists.', status=status.HTTP_200_OK)

    # delete all vars from service context
    def delete(self, request, job_id):
        variables.clear()
        return Response('All vars were removed.', status=status.HTTP_200_OK)


class VarView(APIView):

    # get var_value by var_name from service context
    def get(self, request, job_id, var_name):
        try:
            return Response(variables[var_name], status=status.HTTP_200_OK)
        except TypeError:
            return Response(str(variables[var_name]), status=status.HTTP_200_OK)
        except:
            return Response(f'No such var <{var_name}>.', status=status.HTTP_404_NOT_FOUND)

    # delete var by var_name in service context
    def delete(self, request, job_id, var_name):
        try:
            del variables[var_name]
            return Response(f'Var <{var_name}> was removed.', status=status.HTTP_200_OK)
        except:
            return Response(f'No such var <{var_name}>.', status=status.HTTP_404_NOT_FOUND)


class OperationsView(APIView):
    # write function logic to python script
    def post(self, request, job_id):
        body = json.loads(request.body)
        function_to_call = body['functionname']
        input_var_names = body['inputvars']
        output_var_names = body['outputvars']

        # write line of code to .py file based on request info
        write_op(filename, input_var_names, output_var_names, function_to_call)

        return Response('OK. Successfully create operation.', status=status.HTTP_200_OK)


class JobsView(APIView):
    # submit job on hpc
    def post(self, request):
        print("Service: START JOB")
        # create final python script
        write_imports(filename_final)
        copy_file_content(filename, filename_final)
        # copy it to hpc
        do_remote_bash_cmd(
            "scp -i /Users/someo/.ssh/id_rsa " + filename_final + " gorodnichev_m_a@84.237.88.44:/home/fano.icmmg/gorodnichev_m_a/aka/processing_modules/workdir/")
        print("Service: SCP PYTHON SCRIPT TO HPC")

        # create cron.sh
        write_sh_script()
        # copy it to hpc
        do_remote_bash_cmd(
            "scp -i /Users/someo/.ssh/id_rsa " + filename_sh + " gorodnichev_m_a@84.237.88.44:/home/fano.icmmg/gorodnichev_m_a/aka/processing_modules/workdir/")
        print("Service: SCP SH SCRIPT TO HPC")

        # 1 way
        # submit job on hpc
        # out = do_remote_bash_cmd("ssh gorodnichev_m_a@nks-1p.sscc.ru -i /Users/someo/.ssh/id_rsa \"cd aka/processing_modules/workdir; dos2unix cron.sh; sbatch cron.sh\"")
        # job_id = re.findall(r'\d+', out)[0]
        # print("SUBMIT JOB ON HPC", job_id)

        # 2 way
        # another way of doing processing when cluster queue is stack
        out = do_remote_bash_cmd(
            "ssh gorodnichev_m_a@nks-1p.sscc.ru -i /Users/someo/.ssh/id_rsa \"cd aka/processing_modules/workdir; source ../../env/bin/activate; python full_proc_eeg.py; deactivate\"")
        print("Service: DONE PROCESSING")

        # wait for job execution (only if the way 1 was used)
        # while job_is_alive(job_id):
        #     time.sleep(5)

        # clean files
        clean_file(filename)
        clean_file(filename_final)
        clean_file(filename_sh)
        return Response('Job completed.\n' + str(out), status=status.HTTP_200_OK)


class JobView(APIView):
    # get results of completed job
    def get(self, request, job_id):
        # get names and dates of two last modified files -- pngs that were created while this job execution
        output = do_remote_bash_cmd("ssh gorodnichev_m_a@nks-1p.sscc.ru -i /Users/someo/.ssh/id_rsa \"cd aka/processing_modules/workdir/psd_pngs; ls -tl | head -n 3\"")
        name1, date1, name2, date2 = save_paths_and_dates(output)

        # load name1 and name2 pngs from remote to local dir in Aka MiniApp
        do_remote_bash_cmd(
            "scp -p -i /Users/someo/.ssh/id_rsa gorodnichev_m_a@84.237.88.44:/home/fano.icmmg/gorodnichev_m_a/aka/processing_modules/workdir/psd_pngs/"
            + name1
            + " /Users/someo/PycharmProjects/aka-client-web-fix-fix/miniapp/res/")
        do_remote_bash_cmd(
            "scp -p -i /Users/someo/.ssh/id_rsa gorodnichev_m_a@84.237.88.44:/home/fano.icmmg/gorodnichev_m_a/aka/processing_modules/workdir/psd_pngs/"
            + name2
            + " /Users/someo/PycharmProjects/aka-client-web-fix-fix/miniapp/res/")
        print("Service: PNGS WERE LOADED")

        return Response('Pngs were loaded.\n' + name1 + "|" + date1 + "\n" + name2 + "|" + date2,
                        status=status.HTTP_200_OK)


# example of line which is needed to be parsed
# "total 6
# -rw-r--r-- 1 gorodnichev_m_a fano.icmmg 37533 Jun 12 12:33 EC-Multitaper-PSD-gradiometers-,Европеоиды,первый-год,11,Fon1,Co_011_v1_fon1.set.png
# -rw-r--r-- 1 gorodnichev_m_a fano.icmmg 36399 Jun 12 12:33 EO-Multitaper-PSD-gradiometers-,Европеоиды,первый-год,11,Fon1,Co_011_v1_fon1.set.png"
# example of dict element parsed from this line
# 'Европеоиды/первый год/11/Fon1/Co_011_v1_fon1.set': 'Jun 12 12:33'
def save_paths_and_dates(out):
    dates = re.findall(r'(Jun?|May?) ([0-9][0-9] [0-9][0-9]:[0-9][0-9])', out)
    names = re.findall(r'((EO|EC).+\.png)', out)
    path = names[0][0].replace("EO-Multitaper-PSD-gradiometers-,", "") \
        .replace("EC-Multitaper-PSD-gradiometers-,", "") \
        .replace(".png", "") \
        .replace("-", " ") \
        .replace(",", "/")
    paths_dates[path] = dates[0][0] + " " + dates[0][1]
    return names[0][0], dates[0][0] + " " + dates[0][1], names[1][0], dates[1][0] + " " + dates[1][1]


class PathsView(APIView):
    # get saved paths to .set files and dates of processing
    def get(self, request):
        return Response(str(paths_dates), status=status.HTTP_200_OK)