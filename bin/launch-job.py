#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import glob
import configparser
import argparse
import subprocess
import uuid
from pathlib import Path

# ------------------------------------------------------------------------------
# Configuration Class (Reused from plant-pipeline.py)
# ------------------------------------------------------------------------------
class Configuration:
    """Session configuration"""
    config = configparser.ConfigParser()

    def __enter__(self):
        self.config.add_section('general')
        self.config.add_section('paths')
        self.config.read(self.name())
        return self

    def name(self):
        return ('%s/.plant-pipeline.ini' % os.path.expanduser('~'))

    def section(self,section):
        dict1 = {}
        try:
            options = self.config.options(section)
        except:
            return None
        for option in options:
            try:
                dict1[option] = self.config.get(section, option)
            except:
                dict1[option] = None
        return dict1

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def get_project_dir(config):
    general = config.section('general')
    if general and 'project_dir' in general:
        return general['project_dir']
    return None

def list_pipeline_scripts(project_dir):
    script_dir = os.path.join(project_dir, 'pipeline_scripts')
    if not os.path.isdir(script_dir):
        return []
    return glob.glob(os.path.join(script_dir, '*.sh'))

def get_user_input(prompt, default=None):
    if default:
        user_input = input(f"{prompt} [{default}]: ")
        return user_input.strip() or default
    else:
        return input(f"{prompt}: ").strip()

def generate_job_yaml(job_name, script_path, cpu_req, cpu_lim, mem_req, mem_lim, project_dir):
    # Construct log file path in the same directory as the script
    script_name = os.path.basename(script_path)
    log_file = os.path.join(os.path.dirname(script_path), f"{script_name}.log")
    
    # Command to run: source venv, run script, redirect output
    # Note: We use the same venv path as in the dev pod
    venv_path = "/home/user1000/workspace/nbgw/bin/activate"
    cmd = f"source {venv_path} && {script_path} > {log_file} 2>&1"

    # YAML Template
    yaml_template = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  namespace: chlup-ns
spec:
  ttlSecondsAfterFinished: 86400 # Keep for 1 day
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      
      # --- POD SECURITY ---
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        fsGroupChangePolicy: "OnRootMismatch"
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault

      containers:
      - name: pipeline-job
        image: chlupacthebosmer/illumina-pipeline:v4
        imagePullPolicy: Always
        
        # --- SECURITY ---
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
          runAsNonRoot: true
          runAsUser: 1000

        command: ["/bin/bash", "-c"]
        args:
          - "{cmd}"
        resources:
          requests:
            cpu: "{cpu_req}"
            memory: "{mem_req}"
          limits:
            cpu: "{cpu_lim}"
            memory: "{mem_lim}"
        volumeMounts:
        - mountPath: /home/user1000/workspace
          name: illumina-storage
        - mountPath: /dev/shm
          name: dshm
        - mountPath: /tmp
          name: tmp-vol

      volumes:
      - name: illumina-storage
        persistentVolumeClaim:
          claimName: illumina-pvc
      - name: dshm
        emptyDir:
          medium: Memory
      - name: tmp-vol
        emptyDir: {{}}
"""
    return yaml_template

# ------------------------------------------------------------------------------
# Main Logic
# ------------------------------------------------------------------------------
def main():
    with Configuration() as config:
        project_dir = get_project_dir(config)
        
        if not project_dir:
            print("Error: Project directory not set in .plant-pipeline.ini")
            sys.exit(1)

        print(f"Current Project Directory: {project_dir}")
        
        scripts = list_pipeline_scripts(project_dir)
        if not scripts:
            print(f"No .sh scripts found in {project_dir}/pipeline_scripts")
            sys.exit(1)

        print("\nAvailable Pipeline Scripts:")
        for i, script in enumerate(sorted(scripts)):
            print(f"{i + 1}: {os.path.basename(script)}")

        try:
            selection = int(get_user_input("\nSelect a script to run (number)"))
            if selection < 1 or selection > len(scripts):
                raise ValueError
            selected_script = sorted(scripts)[selection - 1]
        except ValueError:
            print("Invalid selection.")
            sys.exit(1)

        print(f"\nSelected: {selected_script}")

        # Resource Requests
        cpu_req = get_user_input("CPU Request", default="1")
        mem_req = get_user_input("Memory Request (e.g. 4Gi)", default="4Gi")

        # Calculate limits (simple heuristic)
        # For CPU, add 0.5 or 50%? Let's generic loose limits: +1 core
        # For Memory, add 2Gi
        # Parsing "1" -> 1.0. Parsing "1000m" -> 1.0
        # This is string manipulation, keeping it simple for now
        
        # Simple limit logic: request same as limit or slightly higher? 
        # User asked for "automatically increase limits by a small margin"
        # Let's assume input is simple integers or standard K8s strings
        
        cpu_lim = cpu_req 
        if cpu_req.isdigit():
             cpu_lim = str(int(cpu_req) + 1)
        elif "m" in cpu_req:
             # e.g. 500m -> 1000m (add 500m)
             val = int(cpu_req.replace("m", ""))
             cpu_lim = f"{val + 500}m"

        mem_lim = mem_req
        if "Gi" in mem_req:
            val = int(mem_req.replace("Gi", ""))
            mem_lim = f"{val + 2}Gi"
        elif "Mi" in mem_req:
            val = int(mem_req.replace("Mi", ""))
            mem_lim = f"{val + 512}Mi"
        
        print(f"\nConfiguration:")
        print(f"  Script: {selected_script}")
        print(f"  CPU: {cpu_req} (Limit: {cpu_lim})")
        print(f"  Mem: {mem_req} (Limit: {mem_lim})")

        confirm = get_user_input("\nLaunch Job? (y/n)", default="y")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

        # Generate Unique Job Name
        # clean script name (lowercase, no extension, replace underscores with dashes)
        clean_name = os.path.basename(selected_script).lower().replace('.sh', '').replace('_', '-')
        # truncate to allowed char length for k8s names if needed, usually 63 chars
        # Add short ID
        job_id = str(uuid.uuid4())[:5]
        job_name = f"pipeline-{clean_name}-{job_id}"

        yaml_content = generate_job_yaml(job_name, selected_script, cpu_req, cpu_lim, mem_req, mem_lim, project_dir)
        
        print(f"\nGenerating Job: {job_name}")
        
        # Apply to Kubernetes
        try:
            # We pipe the YAML to stdin of kubectl
            process = subprocess.Popen(['kubectl', 'apply', '-f', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=yaml_content)
            
            if process.returncode == 0:
                print("\nJob submitted successfully!")
                print(stdout)
                print(f"Logs will be written to: {os.path.join(os.path.dirname(selected_script), os.path.basename(selected_script) + '.log')}")
                print(f"Monitor with: kubectl get jobs")
            else:
                print("\nError submitting job:")
                print(stderr)
        except Exception as e:
            print(f"Failed to execute kubectl: {e}")

if __name__ == "__main__":
    main()
