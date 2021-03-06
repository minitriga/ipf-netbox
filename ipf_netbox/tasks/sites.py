import asyncio

from tabulate import tabulate
from operator import itemgetter
from httpx import Response

from ipf_netbox.collection import get_collection
from ipf_netbox.diff import diff
from ipf_netbox.netbox.source import NetboxClient
from ipf_netbox.tasks.tasktools import with_sources


@with_sources
async def ensure_sites(ipf, nb, dry_run):
    """
    Ensure Netbox contains the sites defined in IP Fabric
    """
    print("Ensure Netbox contains the Sites defined in IP Fabric")
    print("Fetching from IP Fabric and Netbox ... ")

    source_ipf = ipf
    source_netbox = nb

    col_ipf = get_collection(source=source_ipf, name="sites")
    col_netbox = get_collection(source=source_netbox, name="sites")

    await asyncio.gather(col_ipf.fetch(), col_netbox.fetch())

    col_ipf.make_keys()
    col_netbox.make_keys()

    print(f"IP Fabric {len(col_ipf)} items.")
    print(f"Netbox {len(col_netbox)} items.")

    diff_res = diff(source_from=col_ipf, sync_to=col_netbox)

    if diff_res is None:
        print("No changes required.")
        return

    _dry_report(source_col=col_ipf, diff_res=diff_res)

    if dry_run:
        return

    await _execute_changes(nb=source_netbox.client, diff_res=diff_res)


async def _execute_changes(nb: NetboxClient, diff_res):
    # for each of the sites that do not exist, create one

    def _report(_task: asyncio.Task):
        res: Response = _task.result()
        name = _task.get_name()
        if res.is_error:
            print(f"CREATE site: {name}: FAIL: {res.text}")
            return
        print(f"CREATE site: {name}: OK")

    tasks = [
        asyncio.create_task(
            coro=nb.post(url="/dcim/sites/", json={"name": name, "slug": name}),
            name=name,
        )
        for name in diff_res.missing
    ]

    [_t.add_done_callback(_report) for _t in tasks]

    await asyncio.gather(*tasks, return_exceptions=True)


def _dry_report(source_col, diff_res):

    tab_data = [
        [key, ["Yes", "No"][key in diff_res.missing]] for key in source_col.inventory
    ]
    tab_data.sort(key=itemgetter(0))

    print(tabulate(headers=["Site Name", "Exists"], tabular_data=tab_data))
