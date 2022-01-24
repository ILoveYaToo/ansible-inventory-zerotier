from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleError, AnsibleParserError
import requests


class InventoryModule(BaseInventoryPlugin):
    NAME = "zerotier"  # used internally by Ansible, it should match the file name but not required

    def verify_file(self, path):
        """return true/false if this is possibly a valid file for this plugin to consume"""
        valid = False
        if super(InventoryModule, self).verify_file(path):
            # base class verifies that file exists and is readable by current user
            if path.endswith(("zerotier_inventory.yaml", "zerotier_inventory.yml")):
                valid = True
        return valid

    def parse(self, inventory, loader, path, cache):
        # call base method to ensure properties are available for use with other helper methods
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        # Process API Options
        my_config = self._read_config_data(path)

        try:
            self.zt_api_url = my_config.get("zt_api_url")
            self.zt_api_key = my_config.get("zt_api_key")
            self.zt_network_id = my_config.get("zt_network_id")
        except Exception as e:
            raise AnsibleParserError("All correct options required: {}".format(e))

        self.zt_network_tags = self.zerotier_get_network_tags(
            zt_api_url=self.zt_api_url,
            zt_api_key=self.zt_api_key,
            zt_network_id=self.zt_network_id,
        )
        self.zt_hosts = self.zerotier_get_network_hosts(
            zt_api_url=self.zt_api_url,
            zt_api_key=self.zt_api_key,
            zt_network_id=self.zt_network_id,
            zt_network_tags=self.zt_network_tags[2],
        )

        # Convert zt_hosts and zt_network_tags into inventory
        self.zerotier_process_hosts(
            zt_hosts=self.zt_hosts, zt_network_tags=self.zt_network_tags[2]
        )

    # Formats ZT tags in a queryable format
    def zerotier_format_tags(self, zt_api_tag_response):
        zt_tags = {}
        for tag, tag_properties in zt_api_tag_response.items():
            zt_tags[tag_properties["id"]] = {}
            zt_tags[tag_properties["id"]]["name"] = tag
            zt_tags[tag_properties["id"]]["enums"] = {}
            # For some reason, when querying for members of a network, the enums are written using IDs instead of names
            # But we still need the IDs for format the groups!
            # Enums should be unique anyways, swapping them should be fine...
            zt_tags[tag_properties["id"]]["enums"] = dict(
                (v, k) for k, v in tag_properties["enums"].items()
            )
        return zt_tags

    # Check if ZT Central is online
    def zerotier_check_server_status(self, zt_api_url):
        headers = {"Content-type": "application/json", "Accept": "application/json"}
        zt_server_status = requests.get(zt_api_url + "/api/status", headers=headers)
        if zt_server_status.status_code == requests.codes.ok:
            return True
        else:
            return False

    # Get network tags in ZT network
    def zerotier_get_network_tags(self, zt_api_url, zt_api_key, zt_network_id):
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "Authorization": "bearer " + zt_api_key,
        }
        zt_network_info = requests.get(
            zt_api_url + "/api/v1/network/" + zt_network_id, headers=headers
        )
        if zt_network_info.status_code == requests.codes.ok:
            zt_api_response = zt_network_info.json()
            # Get tags in network
            zt_tags = self.zerotier_format_tags(
                zt_api_tag_response=zt_api_response["tagsByName"]
            )
            return (True, "Tags exist in this network", zt_tags)
        # Return error based on ZT API docs
        elif zt_network_info.status_code == 403:
            return (
                False,
                "API Key does not have access to Zerotier Network ID " + zt_network_id,
            )
        # Return error based on ZT API docs
        elif zt_network_info.status_code == 404:
            return (False, "Zerotier Network ID " + zt_network_id + " Not Found")
        # Catch all errors
        else:
            return (False, "Unknown Zerotier Network Error")

    # Convert ZT hosts into ansible inventory
    def zerotier_process_hosts(self, zt_hosts, zt_network_tags):
        for host in zt_hosts:
            # Make sure host is not hidden, has at least one internal IP, and is authorized
            if (
                host["hidden"] == False
                and len(host["config"]["ipAssignments"]) > 0
                and host["config"]["authorized"] == True
            ):  
                # Get tags
                # If tag does not resolve to anything in the zerotier tag database, we just do not add it...
                for tag in host["config"]["tags"]:
                #    # Check if both tag and enum is defined in network
                    if (
                        tag[0] in zt_network_tags.keys()
                        and tag[1] in zt_network_tags[tag[0]]["enums"].keys()
                    ):
                        # Primary Group
                        zt_group_primary = zt_network_tags[tag[0]]["name"]
                        # Secondary Group
                        zt_group_child = zt_network_tags[tag[0]]["enums"][tag[1]]
                        # Create Groups
                        self.inventory.add_group(zt_group_primary)
                        self.inventory.add_group(zt_group_child)
                        # Assign Child Group to Primary Group
                        self.inventory.add_child(zt_group_primary, zt_group_child)
                        # Create Host
                        self.inventory.add_host(host=host["nodeId"],group=None)
                        # Assign Host to Child Group
                        self.inventory.add_child(zt_group_child, host["nodeId"])

                        # Set Host variables
                        self.inventory.set_variable(host["nodeId"], "node_name", host["name"])
                        self.inventory.set_variable(
                            host["nodeId"], "description", host["description"]
                        )
                        self.inventory.set_variable(
                            host["nodeId"], "ansible_host", host["config"]["ipAssignments"][0]
                        )

    # Get hosts in specified ZT network
    def zerotier_get_network_hosts(
        self, zt_api_url, zt_api_key, zt_network_id, zt_network_tags
    ):
        headers = {
            "Content-type": "application/json",
            "Accept": "text/plain",
            "Authorization": "bearer " + zt_api_key,
        }
        zt_network_members_raw = requests.get(
            zt_api_url + "/api/v1/network/" + zt_network_id + "/member", headers=headers
        )
        zt_network_members = zt_network_members_raw.json()
        return zt_network_members
