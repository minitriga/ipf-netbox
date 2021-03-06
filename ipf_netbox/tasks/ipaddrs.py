import asyncio

from httpx import Response

from ipf_netbox.collection import get_collection
from ipf_netbox.diff import diff, DiffResults
from ipf_netbox.tasks.tasktools import with_sources
from ipf_netbox.ipfabric.ipaddrs import IPFabricIPAddrCollection
from ipf_netbox.netbox.ipaddrs import NetboxIPAddrCollection


@with_sources
async def ensure_ipaddrs(ipf, nb, **params) -> IPFabricIPAddrCollection:
    print("\nEnsure IP Address.")

    print("Fetching from IP Fabric ... ", flush=True, end="")

    ipf_col: IPFabricIPAddrCollection = get_collection(  # noqa
        source=ipf, name="ipaddrs"
    )

    if (filters := params.get("filters")) is not None:
        await ipf_col.fetch(filters=filters)

    elif (ipf_col_ifaces := params.get("interfaces")) is not None:

        device_list = {rec["hostname"] for rec in ipf_col_ifaces.inventory.values()}
        print(f"{len(device_list)} devices ... ", flush=True, end="")

        await asyncio.gather(
            *(
                ipf_col.fetch(filters=f"hostname = {hostname}")
                for hostname in device_list
            )
        )

    else:
        raise RuntimeError("FAIL: No parameters to fetch ipaddrs")

    ipf_col.make_keys()

    if not len(ipf_col.source_records):
        print(f"0 items matching filter: `{filters}`.")
        return ipf_col

    print(f"{len(ipf_col)} items.")

    # -------------------------------------------------------------------------
    # Need to fetch from Netbox on a per-device basis.
    # -------------------------------------------------------------------------

    print("Fetching from Netbox ... ", flush=True, end="")

    nb_col: NetboxIPAddrCollection = get_collection(source=nb, name="ipaddrs")  # noqa

    device_list = {rec["hostname"] for rec in ipf_col.inventory.values()}
    print(f"{len(device_list)} devices ... ", flush=True, end="")

    nb.client.timeout = 120
    await asyncio.gather(*(nb_col.fetch(hostname=hostname) for hostname in device_list))

    nb_col.make_keys()
    print(f"{len(nb_col)} items.", flush=True)

    # -------------------------------------------------------------------------
    # check for differences and process accordingly.
    # -------------------------------------------------------------------------

    diff_res = diff(source_from=ipf_col, sync_to=nb_col)
    if not diff_res:
        print("No changes required.")
        return

    _diff_report(diff_res)

    if params.get("dry_run", False) is True:
        return

    tasks = list()
    if diff_res.missing:
        tasks.append(_diff_create(nb_col, diff_res.missing))

    if diff_res.changes:
        tasks.append(_diff_update(nb_col, diff_res.changes))

    await asyncio.gather(*tasks)


def _diff_report(diff_res: DiffResults):
    print("\nDiff Report")
    print(f"   Missing: count {len(diff_res.missing)}")
    print(f"   Needs Update: count {len(diff_res.changes)}")
    print("\n")


async def _diff_update(nb_col: NetboxIPAddrCollection, changes):
    def _done(_key, res: Response):
        # res: Response = _task.result()
        _hostname, _ifname = _key
        res.raise_for_status()
        print(f"UPDATE:OK: ipaddr {_hostname}, {_ifname}", flush=True)

    await nb_col.update_changes(changes=changes, callback=_done)


async def _diff_create(nb_col: NetboxIPAddrCollection, missing):
    def _done(item, _res: Response):
        _res.raise_for_status()
        print(
            f"CREATE:OK: ipaddr {item['hostname']}, {item['interface']}, {item['ipaddr']}",
            flush=True,
        )

    await nb_col.create_missing(missing, callback=_done)
