from typing import Dict, Tuple, Any

from aioipfabric.filters import parse_filter

from ipf_netbox.collection import Collection
from ipf_netbox.collections.ipaddrs import IPAddrCollection
from ipf_netbox.ipfabric.source import IPFabricSource
from ipf_netbox.mappings import normalize_hostname, expand_interface


class IPFabricIPAddrCollection(Collection, IPAddrCollection):
    source_class = IPFabricSource

    async def fetch(self, **params):

        if (filters := params.get("filters")) is not None:
            params["filters"] = parse_filter(filters)

        async with self.source.client as ipf:
            return await ipf.fetch_table(
                url="tables/addressing/managed-devs",
                columns=["hostname", "intName", "siteName", "ip", "net"],
                **params,
            )

    def fingerprint(self, rec: Dict) -> Tuple[Any, Dict]:
        try:
            pflen = rec["net"].split("/")[-1]
        except AttributeError:
            pflen = "32"

        return (
            None,
            {
                "ipaddr": f"{rec['ip']}/{pflen}",
                "interface": expand_interface(rec["intName"]),
                "hostname": normalize_hostname(rec["hostname"]),
                "site": rec["siteName"],
            },
        )