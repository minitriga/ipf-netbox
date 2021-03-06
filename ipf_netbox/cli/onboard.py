import asyncio

from ipf_netbox.cli.__main__ import cli
from ipf_netbox.tasks.devices import ensure_devices
from ipf_netbox.tasks.ipaddrs import ensure_ipaddrs
from ipf_netbox.tasks.interfaces import ensure_interfaces

from . import cli_opts


@cli.command(name="onboard")
@cli_opts.opt_dry_run
@cli_opts.opt_force_primary_ip
@cli_opts.opt_device_filter
def cli_onboard(**params):
    """
    Onboard device(s).
    """

    async def onboard_devices():
        ipf_col_devs = await ensure_devices(**params)

        params.pop("filters", None)
        params["devices"] = ipf_col_devs
        params["interfaces"] = await ensure_interfaces(**params)
        await ensure_ipaddrs(**params)

    asyncio.run(onboard_devices())
