# GCP Account Migration Guide

Migrating the disk image across two completely different Google Cloud accounts requires complicated, cross-project permission linking. However, because we brilliantly automated your entire infrastructure using Docker and GitHub Actions, **the easiest and fastest way to migrate is to simply launch a fresh VM and let GitHub deploy it!**

Follow this checklist to move your project across accounts in roughly 15 minutes:

### Phase 1: Create the new VM
1. Log into your new Google Cloud account.
2. Go to **Compute Engine -> VM Instances** and click **Create Instance**.
3. Under Machine Configuration, select **GPUs** and pick an **NVIDIA T4** (or V100). *Note: T4 GPUs are significantly cheaper and almost never run out of stock*.
4. Ensure the machine type is at least **`n1-standard-4`** (15GB RAM).
5. Change the Boot Disk to **Ubuntu 22.04 LTS**.
6. Check the box to **Allow HTTP traffic**.
7. Click **Create**!

### Phase 2: Install GPU Drivers & Docker
SSH into the new VM from the GCP browser console. Paste this master script to automatically install the NVIDIA drivers, Docker, and the GPU Toolkit:
```bash
# 1. Install NVIDIA Drivers
sudo apt update
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall

# 2. Install Docker
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 3. Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```
Once that massive script finishes running, **type `sudo reboot`**, hit Enter, and wait 60 seconds for the VM to restart.

### Phase 3: Link to GitHub Actions
SSH back into your newly rebooted VM. Let's create the connection tunneling keys:
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/github_actions -N "" -q
cat ~/.ssh/github_actions
```
1. Block-copy that enormous private key block output.
2. Go to your **GitHub Repository** -> **Settings** -> **Secrets and Variables** -> **Actions**.
3. Click the pencil icon to update your secrets:
   - `VM_SSH_KEY`: Paste the new private key.
   - `VM_HOST`: Paste the new VM's External IP address.
   - `VM_USERNAME`: Update this if your new GCP account uses a different Google email handle (it is the name before the `@instance` in your terminal).

**Authorize the Key on GCP**
```bash
cat ~/.ssh/github_actions.pub
```
Copy the public key output. Go to the new VM's Details page in Google Cloud Console, click **EDIT**, scroll down to **SSH Keys**, click **ADD ITEM**, paste it in, and hit **SAVE**.

### Phase 4: Deploy and Index
1. Go to your GitHub repository's **Actions** tab, click your pipeline, and hit **Re-run all jobs**. GitHub will instantly connect to the new VM and launch your Docker container!
2. Go back to your VM terminal and let's create our Swapfile so Python doesn't crash during indexing:
```bash
sudo fallocate -l 10G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```
3. Finally, jump into the container and regenerate the medical indexes!
```bash
docker exec -it mediguide-app /bin/bash
python scripts/download_open_corpora.py
python scripts/build_indexes.py
```

By the time you grab a cup of coffee, your application will be flawlessly relocated to the new account!
