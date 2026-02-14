# SSD media drive setup (Jellyfin) on lenovo_server

This prepares the external SSD on **lenovo_server** (192.168.1.12) as a media drive at `/mnt/ssd_media` for Jellyfin. It follows the “Storage Host” steps from the Gemini instructions; NFS and other Swarm nodes can be set up later.

## 1. Check the disk on the server

While SSH’d in (`ssh lenovo_server`), confirm the disk and partition:

```bash
lsblk
lsblk -f
```

- Use the **partition** for data (e.g. `/dev/sdb2` for the 3.6T partition), not the whole disk (`/dev/sdb`).
- If `lsblk -f` shows no `FSTYPE` for that partition, it needs to be formatted.

## 2. Configure and run Ansible (recommended)

1. In **host_vars/lenovo_server.yml**:
   - `ssd_media_device`: partition to use (e.g. `"/dev/sdb2"`).
   - `ssd_media_format`: set to `true` **only** when you intend to format (this wipes the partition). After the first run, set back to `false`.

2. From your control machine (where Ansible runs):

   ```bash
   ansible-playbook prepare_ssd_media.yml
   ```

3. The playbook will:
   - Create `/mnt/ssd_media`
   - Optionally format the partition as ext4 (only when `ssd_media_format: true`)
   - Add an fstab entry by **UUID** and mount the drive

## 3. Manual alternative (run on the server over SSH)

If you prefer not to use Ansible for this:

```bash
# Create mount point
sudo mkdir -p /mnt/ssd_media

# Format only if the partition is not already ext4 (THIS WIPES THE PARTITION)
sudo mkfs.ext4 /dev/sdb2

# Get UUID (use this in fstab)
sudo blkid -s UUID -o value /dev/sdb2

# Mount temporarily to test
sudo mount /dev/sdb2 /mnt/ssd_media

# Add to fstab (replace YOUR-UUID-HERE with output of blkid above)
echo 'UUID=YOUR-UUID-HERE /mnt/ssd_media ext4 defaults 0 2' | sudo tee -a /etc/fstab

# Remount from fstab to verify
sudo umount /mnt/ssd_media
sudo mount -a
df -h /mnt/ssd_media
```

## 4. Transferring files from Windows (FileZilla / WinSCP)

You can use **SFTP** to copy media from your Windows 11 PC to `/mnt/ssd_media`:

- **WinSCP** or **FileZilla**: connect with SSH to `192.168.1.12`, user `thatsmidnight` (or your SSH user), then browse to `/mnt/ssd_media` and upload.
- No Samba is required for this; SSH/SFTP is enough.

## 5. Next steps (from Gemini instructions)

- Set up **NFS server** on lenovo_server and **NFS clients** on the other Swarm nodes so they all see `/mnt/ssd_media`.
- When you deploy Jellyfin (e.g. via Portainer), mount that path (or the NFS share) into the container.

## Summary

| Item            | Value                    |
|-----------------|--------------------------|
| Storage Host    | lenovo_server (192.168.1.12) |
| Partition       | e.g. `/dev/sdb2` (set in host_vars) |
| Mount point     | `/mnt/ssd_media`         |
| File transfer   | WinSCP or FileZilla over SFTP to `/mnt/ssd_media` |
