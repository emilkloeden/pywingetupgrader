# pywingetupgrader

A python script that uses winget to upgrade packages.

## Environment variables

The script searches for three environment variables:

- `WINGET_DEBUG`, default=False, when set to "true" will not upgrade apps, will log more information, and logs apps that would be upgraded, does not ab
  `WINGET_UPGRADE_LEVEL`, default="patch", one of "patch", "minor", "major", or "all", used to filter applications to upgrade based on a degree of tolerance of semantic versioning
  `WINGET_UPGRADE_UNKNOWN_VERSIONS`, default=False, when set to "true" will upgrade applications even if winget cannot identify the version of the installed application. If set to all, all applications will be upgraded.

### Examples

Update patch versions for applications respecting semver (assumes the environment variables have not been set).

```ps
py.exe .\winget_upgrade_parser.py
```

Run in debug mode and list all applications that would be updated when accepting of bumps to major semver versions, including where winget cannot determine the version installed.

```ps
$Env:WINGET_UPGRADE_LEVEL="major"; $Env:WINGET_UPGRADE_UNKNOWN_VERSIONS="true"; $Env:WINGET_DEBUG="true"; py.exe .\winget_upgrade_parser.py
```

## Allowlist and Blocklisting

In addition to using the Environment Variables to control what applications should be upgraded, you can set apps to always upgrade (regardless of use of semantic versioning) by adding their id to the set in the `get_allowed_updates()` function definition. To never update an application, add it's id to to the set in the `get_blocked_updates()` function definition.

Blocklisting takes precedence in the event of a conflict. It also takes precedence over setting the WINGET_UPGRADE_LEVEL to "all".

## Known Issues and Possible Improvements

- Does not use winget logging
- Does not ensure restarts won't occur
- Does not handle cases where winget identifies a new version but won't let you use winget to update it.
- Needs documenting
- Could be modified to use command-line arguments in preference of environment variables.
