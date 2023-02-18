import sys
import requests
import yaml
import time
from datetime import datetime
import os
import pytz

from absl import app
from absl import flags
from absl import logging
from typing import Dict, List

from PIL import Image
from io import BytesIO
from SSIM_PIL import compare_ssim

from threading import Thread

FLAGS = flags.FLAGS

flags.DEFINE_string("config", None, "path to YAML config file")

flags.mark_flag_as_required("config")


def config_load(config_file_path: str) -> List[Dict]:
    with open(config_file_path, "r") as f:
        config = yaml.safe_load(f)
        res = []
        for section in ["server", "cameras", "global"]:
            res.append(config[section])
        return res


def get_pic_from_url(url: str) -> Image:
    try:
        r = requests.get(url)
    except:  # TODO: Maybe more specific handling?
        return None
    return Image.open(BytesIO(r.content))


def get_interval_from_pic(image1: Image, image2: Image):
    x = compare_ssim(image1, image2)
    if not isinstance(x, float):
        logging.warning(
            f"Could not get compute the difference between the last 2 pictures"
        )
        return 10
    logging.debug(f"ssim: {x}")
    return int(
        120 * (max(x, 0.5) - 0.45)
    )  # https://www.wolframalpha.com/input?i=120*%28max%28x%2C0.5%29-0.45%29


def get_pic_fullpath(camera_name: str) -> str:
    tz = pytz.timezone(global_config["timezone"])
    dt = tz.localize(datetime.now())
    return os.path.join(
        global_config["pic_dir"],
        camera_name,
        dt.strftime("%Y-%m-%d"),
        dt.strftime("%Y-%m-%dT%H-%M-%S%Z.jpg"),
    )


def write_pic_to_disk(pic: Image, pic_path: str):
    os.makedirs(os.path.dirname(pic_path), exist_ok=True)
    logging.debug(f"Saving picture {pic_path}")
    pic.save(pic_path)


def snap(camera_name, camera_config: Dict):
    url = camera_config["url"]
    previous_pic_fullpath = get_pic_fullpath(camera_name)
    previous_pic = get_pic_from_url(url)
    sleep_interval = 5
    while True:
        write_pic_to_disk(previous_pic, previous_pic_fullpath)
        logging.debug(f"Sleeping {sleep_interval}s")
        time.sleep(sleep_interval)
        new_pic_fullpath = get_pic_fullpath(camera_name)
        new_pic = get_pic_from_url(url)
        if new_pic is None:
            logging.warning(f"{camera_name}: Could not fetch picture from {url}")
            continue
        sleep_interval = get_interval_from_pic(previous_pic, new_pic)
        previous_pic = new_pic
        previous_pic_fullpath = new_pic_fullpath


def main(argv):
    del argv  # Unused.

    print(
        "Running under Python {0[0]}.{0[1]}.{0[2]}".format(sys.version_info),
        file=sys.stderr,
    )
    global server_config, cameras_config, global_config
    server_config, cameras_config, global_config = config_load(FLAGS.config)
    logging.debug(
        f"Loaded config: server: {server_config} cameras: {cameras_config} global: {global_config}"
    )
    for cam in cameras_config:
        t = Thread(target=snap, daemon=True, name=cam, args=[cam, cameras_config[cam]])
        time.sleep(3)
        logging.info(f"Starting thread {t}")
        t.start()

    while True:
        time.sleep(10)

if __name__ == "__main__":
    app.run(main)
