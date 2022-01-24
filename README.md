# ansible-inventory-zerotier

Allows for a ZeroTier network to be used as an inventory source.

Still a WIP, improvements will come soon.

## Design
This inventory plugin maps human readable tag names to group names in ansible.
ZeroTier Device IDs are used to identify the host, and internal IPs are used by ansible to connect to the hosts.

For example, if you have the following tag definition, host tagged with this combination will show up under the `servertype:ansiblecontroller` ansible group/child group.
```
tag servertype
  id 1001
	enum 1000 ansiblecontroller
```

Note that untagged hosts will not show up at this time. For more information about tagging in ZeroTier, please see https://docs.zerotier.com/zerotier/rules/#33tagsaname3_3a

## Host Vars
A number of host vars are returned at this time, they are as follows.

- `node_name`: name of the node in ZeroTier
- `description`: description of the node in ZeroTier