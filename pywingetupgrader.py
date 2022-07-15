import json
import logging
import os
import re
import subprocess

SEMVER_PATTERN = re.compile("^\d+?\.\d+?\.\d+$")


def get_bool_env_var(key, default):
    return os.environ.get(key, str(default)).lower() == "true"

def get_applications_available_to_upgrade(winget_exe_path):
    try:
        # Hack to ensure source agreements are accepted so that "winget upgrade" command returns
        # results in an expected format
        subprocess.check_output([winget_exe_path, "list", "--accept-source-agreements", "-n", "1"], timeout=15)
        output = subprocess.check_output([winget_exe_path, "upgrade"])
        output = output.decode('utf-8')
        return output
    except FileNotFoundError as exc:
        logging.error(f"Process failed because the winget executable could not be found.")
    except subprocess.CalledProcessError as exc:
        logging.error(
                f"Process failed because it did not return a successful return code. "
                f"Returned {exc.returncode}\n{exc}"
            )
    except subprocess.TimeoutExpired as exc:
        logging.error(f"Process timed out whilst identify apps to upgrade'.\n{exc}")



def extract_applications_from_table(output):
    rows = output.split("\r\n")[:-2]
    headers_and_their_starting_positions = get_headers_and_their_starting_positions(rows)
    
    records = []

    # Start at the third row since the first row is headers and the second a line break
    for row in rows[2:]:
        record = {}
        for i, (key, start_pos) in enumerate(headers_and_their_starting_positions):
            # We don't have end_positions so we reuse the start position of the next header
            if i < len(headers_and_their_starting_positions) - 1:
                _, end_pos = headers_and_their_starting_positions[i+1]
                record[key] = row[start_pos:end_pos].strip()
            # ...except for the final header
            else:
                record[key] = row[start_pos:].strip()
        records.append(record)

    return records


def get_headers_and_their_starting_positions(rows):
    header_row = rows[0]
    headers = [
        v
        for v
        in header_row.split()
        if v.isprintable()
    ]
    first_header_offset = header_row.find(headers[0])
    headers_and_their_starting_positions = [
        (h, header_row.find(h) - first_header_offset)
        for h
        in headers
    ]
    
    return headers_and_their_starting_positions


def get_applications_using_semver(applications):
    return [
        add_semver_details(app)
        for app
        in applications
        if SEMVER_PATTERN.match(app["Version"]) or SEMVER_PATTERN.match(app["Available"])
    ]


def add_semver_details(app):
    if SEMVER_PATTERN.match(app["Version"]):
        major, minor, patch  = app["Version"].split(".")
        app["current_major"] = int(major)
        app["current_minor"] = int(minor)
        app["current_patch"] = int(patch)
    if SEMVER_PATTERN.match(app["Available"]):
        available_major, available_minor, available_patch  = app["Available"].split(".")
        app["available_major"] = int(available_major)
        app["available_minor"] = int(available_minor)
        app["available_patch"] = int(available_patch)
    
    return app


def upgrade_app(app, winget_exe_path):
    __id = app["Id"]
    logging.info(f'Attempting to upgrade {app["Id"]} from version {app["Version"]} to {app["Available"]}')
    
    try:
        subprocess.run([
                winget_exe_path,
                "upgrade", 
                "--silent",
                "--id", 
                __id,
                "--accept-package-agreements",
                "--accept-source-agreements",
                # Commenting out logging as it is quite noisy by default
                # "--log",
                # "./winget-upgrades.log",

                # Commenting out --override as it seems to mess with --silent. Maybe.
                # "--override",
                # '"/norestart"',
            ], timeout=250
        )
    except FileNotFoundError as exc:
        logging.error(f"Process failed to upgrade '{__id}' because the executable could not be found.")
    except subprocess.CalledProcessError as exc:
        logging.error(
                f"Process failed to upgrade '{__id}' because did not return a successful return code. "
                f"Returned {exc.returncode}\n{exc}"
            )
    except subprocess.TimeoutExpired as exc:
        logging.error(f"Process timed out whilst trying to upgrade '{__id}'.\n{exc}")

def get_apps_to_upgrade(applications, upgrade_level, upgrade_unknowns):
    
    applications_using_semver = get_applications_using_semver(applications)

    apps_to_upgrade = []
    
    if upgrade_level.lower() == "all":
        return applications


    apps_with_patch_upgrades = [
        app
        for app
        in applications_using_semver
        if "current_major" in app and "available_major" in app and app["current_major"] == app["available_major"] and app["current_minor"] == app["available_minor"] and app["current_patch"] < app["available_patch"]
    ]

    apps_with_minor_upgrades = [
        app
        for app
        in applications_using_semver
        if "current_major" in app and "available_major" in app and app["current_major"] == app["available_major"] and app["current_minor"] < app["available_minor"]
    ]

    apps_with_major_upgrades = [
        app
        for app
        in applications_using_semver
        if "current_major" in app and "available_major" in app and app["current_major"] < app["available_major"]
    ]

    apps_with_unknown_current_version = [
        app
        for app
        in applications_using_semver
        if app["Version"].lower() == "unknown"
    ]

    if upgrade_level == "patch":
        apps_to_upgrade = apps_with_patch_upgrades

    elif upgrade_level == "minor":
        apps_to_upgrade = apps_with_minor_upgrades + apps_with_patch_upgrades

    elif upgrade_level == "major":
        apps_to_upgrade = apps_with_major_upgrades + apps_with_minor_upgrades + apps_with_patch_upgrades
    
    if upgrade_unknowns:
        apps_to_upgrade += apps_with_unknown_current_version
    
    return apps_to_upgrade


def get_allowed_updates():
    return set([
        'Python.Python.3'
        ])

def add_allowed_updates(apps_to_upgrade, applications):
    allowed_applications = get_allowed_updates()
    allowed_applications_with_upgrades_available = [
        app
        for app
        in applications
        if app["Id"] in allowed_applications
    ]
    return apps_to_upgrade + allowed_applications_with_upgrades_available

def get_blocked_updates():
    return set([
        'EvanCzaplicki.Elm',
        'VMware.WorkstationPro',
        'CoreyButler.NVMforWindows',
    ])

def remove_blocked_updates(apps_to_upgrade):
    blocked_applications = get_blocked_updates()
    return [
        app
        for app
        in apps_to_upgrade
        if app["Id"] not in blocked_applications
    ]

def get_winget_exe_path():
    try:
        winapps_dir_path = "C:\Program Files\WindowsApps"
        dir_path = [
            dir_ 
            for dir_ 
            in os.listdir(winapps_dir_path) 
            if dir_.startswith('Microsoft.DesktopAppInstaller') and dir_.endswith('x64__8wekyb3d8bbwe')
        ][0]

        return os.path.join(winapps_dir_path, dir_path, "winget.exe")
        
    except PermissionError as e:
        raise e
    except IndexError:
        raise FileNotFoundError("Unable to locate winget executable")



def main():
    try:
        WINGET_DEBUG = get_bool_env_var("WINGET_DEBUG", default=False)
        upgrade_level = os.environ.get("WINGET_UPGRADE_LEVEL", "patch").lower()
        upgrade_unknowns = get_bool_env_var("WINGET_UPGRADE_UNKNOWN_VERSIONS", False)

        
        log_level = logging.DEBUG if WINGET_DEBUG else logging.INFO
        logging.basicConfig(level=log_level)
        
        logging.debug("[-] Finding winget executable location...")
        winget_exe_path = get_winget_exe_path()

        logging.debug("[-] Calling 'winget update' to find applications to upgrade...")
        upgradable_applications_table = get_applications_available_to_upgrade(winget_exe_path)
        
        logging.debug("[-] Parsing results...")
        applications = extract_applications_from_table(upgradable_applications_table)
        
        logging.debug("[-] Filtering to include only applications that use semantic versioning...")
        applications_using_semver = get_applications_using_semver(applications)
        
        logging.debug(f"[-] Filtering to include applications to upgrade based on selected upgrade level: '{upgrade_level}' and whether or not unknown applications should be updated: '{upgrade_unknowns}'")
        apps_to_upgrade = get_apps_to_upgrade(applications_using_semver, upgrade_level, upgrade_unknowns)
        
        logging.debug("[-] Adding apps that are always allowed to upgrade")
        apps_to_upgrade = add_allowed_updates(apps_to_upgrade, applications)
        
        logging.debug("[-] Removing apps that are always blocked from upgrading")
        apps_to_upgrade = remove_blocked_updates(apps_to_upgrade)
        
        if WINGET_DEBUG:
            logging.debug("[-] Listing apps that would have been upgraded:")
            for app in apps_to_upgrade:
                logging.debug(json.dumps(app, indent=2))

        else:
            for app in apps_to_upgrade:
                upgrade_app(app, winget_exe_path)
    except PermissionError as e:
        logging.error("Unable to run due to insufficient permissions. Try to rerunning in a system context.")
    except FileNotFoundError as e:
        logging.error(e)
        logging.error(f"FileNotFoundError thrown in main. {winget_exe_path=}")
    except Exception as e:
        logging.error(e)
        logging.error(f"Exception thrown in main. {winget_exe_path=}")


if __name__ == "__main__":
    main()