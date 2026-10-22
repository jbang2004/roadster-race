"""numpy image IO through ffmpeg (no PIL / cv2 here):  read(path) -> HxWx3 uint8,  write(path, arr)"""
import subprocess, numpy as np


def size(path):
    o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip()
    w, h = (int(v) for v in o.split(','))
    return w, h


def read(path):
    w, h = size(path)
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()


def write(path, a):
    a = np.ascontiguousarray(np.clip(a, 0, 255).astype(np.uint8))
    h, w = a.shape[:2]
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-i', '-', path], input=a.tobytes(), check=True)
