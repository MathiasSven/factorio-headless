#! /usr/bin/env nix-shell
#! nix-shell -i python3 -p python3Packages.requests

import hashlib
import json
import logging
import re
from itertools import batched
from pathlib import Path
from typing import TypedDict

import requests

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

type Version = str
type Hash = str
type FileName = str
type HashDict = dict[FileName, Hash]


class Releases(TypedDict):
    stable: Version
    experimental: Version


class VersionsJSON(TypedDict):
    releases: Releases
    # None
    versions: dict[Version, Hash | None]


FACTORIO_ARCHIVE = "https://www.factorio.com/download/archive/"
FACTORIO_RELEASES = "https://factorio.com/api/latest-releases"
FACTORIO_HASHES = "https://factorio.com/download/sha256sums/"
VERSIONS_JSON_FILE = Path("./versions.json")

HASH_FILENAME_FORMAT: list[str] = [
    "factorio-headless_linux_{version}.tar.xz",
    "factorio_headless_x64_{version}.tar.xz",
]


def fetch_available_versions() -> list[Version]:
    logger.info("Fetching available versions")
    archive_page = requests.get(FACTORIO_ARCHIVE).text
    archive_regex = r"\/download\/archive\/([\d\.]+)"
    return re.findall(archive_regex, archive_page)


def fetch_releases() -> Releases:
    logger.info("Fetching releases")
    releases = requests.get(FACTORIO_RELEASES).json()
    stable = releases["stable"]["headless"]
    try:
        experimental = releases["experimental"]["headless"]
    except (KeyError, TypeError):
        experimental = stable

    return Releases(stable=stable, experimental=experimental)


def fetch_hashes() -> HashDict:
    logger.info("Fetching checksums")
    hash_files = requests.get(FACTORIO_HASHES).text.split()
    return dict(batched(hash_files[::-1], 2))  # type: ignore


def gen_download_link(version: Version):
    return f"https://www.factorio.com/get-download/{version}/headless/linux64"


def download_and_calculate_hash(version: Version) -> Hash | None:
    logger.info("Downloading and calculating hash for version %s", version)
    link = gen_download_link(version)
    sha256_hash = hashlib.sha256()

    with requests.get(link, stream=True) as response:
        if response.status_code == 404:
            logger.warning("Version %s has no headless version", version)
            return None
        response.raise_for_status()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def find_hash_for(version: Version, hash_dict: HashDict) -> Hash | None:
    for filename_format in HASH_FILENAME_FORMAT:
        filename_candidate = filename_format.format(version=version)
        if filename_candidate in hash_dict:
            return hash_dict[filename_candidate]
    logger.warning("Couldn't find hash for version %s", version)
    return download_and_calculate_hash(version)


def read_outdated_versions_hash() -> dict[Version, Hash | None]:
    logger.info("Reading current %s file", VERSIONS_JSON_FILE)
    try:
        with VERSIONS_JSON_FILE.open("r") as file:
            cur_versions_json: VersionsJSON = json.load(file)
            return cur_versions_json["versions"]
    except FileNotFoundError:
        logger.info("The file %s doesn't exist", VERSIONS_JSON_FILE)
        return {}


if __name__ == "__main__":
    cur_versions_hash = read_outdated_versions_hash()

    available_versions = fetch_available_versions()
    new_versions = [v for v in available_versions if v not in cur_versions_hash.keys()]
    logger.info("There are %s new versions", len(new_versions))

    versions_hash_to_keep = {
        k: v for k, v in cur_versions_hash.items() if k in available_versions
    }
    logger.info(
        "There are %s versions which are no longer available",
        len(cur_versions_hash) - len(versions_hash_to_keep),
    )

    if new_versions:
        hashes = fetch_hashes()
        new_versions_hash = {k: find_hash_for(k, hashes) for k in new_versions}
    else:
        logger.info("No new versions, skipping checksum fetching")
        new_versions_hash = {}

    data: VersionsJSON = {
        "releases": fetch_releases(),
        "versions": new_versions_hash | versions_hash_to_keep,
    }

    with VERSIONS_JSON_FILE.open("w") as file:
        logger.info("Writing new %s file", VERSIONS_JSON_FILE)
        json.dump(data, file, indent=4)
