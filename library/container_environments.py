#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, division, print_function
import os
import hashlib
import json

from ansible.module_utils.basic import AnsibleModule

TPL_ENV = """# generated by ansible
{% for key, value in item.items() %}
{{ key }}={{ value }}
{%- endfor %}

"""

TPL_PROP = """# generated by ansible
{% for key, value in item.items() %}
{{ key.ljust(30) }} = {{ value }}
{%- endfor %}

"""


class ContainerEnvironments(object):
    """
    """

    def __init__(self, module):
        """
        """
        self.module = module

        self.base_directory = module.params.get("base_directory")
        self.container = module.params.get("container")
        self.owner = module.params.get("owner")
        self.group = module.params.get("group")
        self.mode = module.params.get("mode")

    def run(self):
        """
        """
        result = dict(
            changed=False,
            failed=True,
            msg="initial"
        )

        result_state = []

        for c in self.container:
            """
            """
            name = c.get("name")
            environments  = c.get("environments", {})
            properties = c.get("properties", {})
            property_files = c.get("property_files", [])
            defined_environments = (len(environments) > 0)
            defined_properties = (len(properties) > 0)
            defined_property_files = (len(property_files) > 0)

            changed = False
            e_changed = False
            p_changed = False

            state = []

            # self.module.log(f"name: {name}")
            # self.module.log("------------------------------------------------------")
            # self.module.log(f"  environments  : {environments} ({len(environments)})")
            # self.module.log(f"  properties    : {properties} ({len(properties)})")
            # self.module.log(f"  property_files: {property_files} ({len(property_files)})")

            """
              write environments
            """
            e_changed = self._write_environments(
                container_name=name,
                environments=environments
            )

            if defined_environments:
                _ = c.pop("environments")

            if e_changed:
                state.append("container.env")

            if defined_properties or defined_property_files:
                """
                  write properties
                """
                property_filename = f"{name}.properties"

                property_files.append({"name": property_filename, "properties": properties})

                for prop in property_files:
                    property_filename = prop.get("name", None)
                    properties = prop.get("properties", {})

                    _changed = self._write_properties(
                        container_name=name,
                        property_filename=property_filename,
                        properties=properties
                    )

                    if _changed:
                        p_changed = True
                        state.append(property_filename)

                if defined_properties:
                    _ = c.pop("properties")

                if defined_property_files:
                    _ = c.pop("property_files")

            if e_changed or p_changed:
                changed = True

            if changed:
                # add recreate to dictionary
                c['recreate'] = True

                res = {}
                state = ", ".join(state)
                state += " successful written"

                res[name] = dict(
                    # changed=True,
                    state=state
                )

                result_state.append(res)

        # define changed for the running tasks
        # migrate a list of dict into dict
        combined_d = {key: value for d in result_state for key, value in d.items()}
        # find all changed and define our variable
        # changed = (len({k: v for k, v in combined_d.items() if v.get('changed') and v.get('changed') == True}) > 0) == True
        changed = (len({k: v for k, v in combined_d.items() if v.get('state')}) > 0)

        result = dict(
            changed = changed,
            failed = False,
            container_data = self.container,
            msg = result_state
        )

        return result

    def _write_environments(self, container_name, environments = {}):
        """
        """
        checksum_file = os.path.join(self.base_directory, container_name, "container.env.checksum")
        data_file     = os.path.join(self.base_directory, container_name, "container.env")

        # if len(environments) == 0:
        #     if os.path.exists(data_file):
        #         os.remove(data_file)
        #     if os.path.exists(checksum_file):
        #         os.remove(checksum_file)
        #
        #     return False

        changed, new_checksum, old_checksum = self.__has_changed(data_file, environments)

        if changed:
            self.__write_template("environments", environments, data_file, new_checksum, checksum_file)

        return changed

    def _write_properties(self, container_name, property_filename, properties = {}):
        """
        """
        checksum_file = os.path.join(self.base_directory, container_name, f"{property_filename}.checksum")
        data_file     = os.path.join(self.base_directory, container_name, property_filename)

        if len(properties) == 0:
            if os.path.exists(data_file):
                os.remove(data_file)
            if os.path.exists(checksum_file):
                os.remove(checksum_file)

            return False

        changed, new_checksum, old_checksum = self.__has_changed(data_file, properties)

        if changed:
            self.__write_template("properties", properties, data_file, new_checksum, checksum_file)

        return changed

    def __write_template(self, env, data, data_file, checksum, checksum_file):
        """
        """
        if isinstance(data, dict):
            """
                sort data
            """
            data = json.dumps(data, sort_keys=True)
            if isinstance(data, str):
                data = json.loads(data)

        data = self.__templated_data(env, data)

        with open(data_file, "w") as f:
            f.write(data)

            with open(checksum_file, "w") as f:
                f.write(checksum)

    def __has_changed(self, data_file, data):
        """
        """
        checksum_file = os.path.join(f"{data_file}.checksum")

        old_checksum = ""

        if not os.path.exists(data_file) and os.path.exists(checksum_file):
            """
            """
            os.remove(checksum_file)

        if os.path.exists(checksum_file):
            with open(checksum_file, "r") as f:
                old_checksum = f.readlines()[0]

        if isinstance(data, dict):
            _data = json.dumps(data, sort_keys=True)
        else:
            _data = data.copy()

        checksum = self.__checksum(_data)
        changed = not (old_checksum == checksum)

        # self.module.log(msg=f" - new  checksum '{checksum}'")
        # self.module.log(msg=f" - curr checksum '{old_checksum}'")
        # self.module.log(msg=f" - changed       '{changed}'")

        return changed, checksum, old_checksum

    def __checksum(self, plaintext):
        """
        """
        password_bytes = plaintext.encode('utf-8')
        password_hash = hashlib.sha256(password_bytes)
        return password_hash.hexdigest()

    def __templated_data(self, env, data):
        """
          generate data from dictionary
        """
        if env == "environments":
            tpl = TPL_ENV
        if env == "properties":
            tpl = TPL_PROP

        from jinja2 import Template

        tm = Template(tpl)
        d = tm.render(item=data)

        return d

# ===========================================
# Module execution.


def main():
    """
    """
    module = AnsibleModule(
        argument_spec=dict(
            base_directory = dict(
                required=True,
                type='str'
            ),
            container = dict(
                required=True,
                type='list'
            ),
            owner=dict(
                required=False
            ),
            group=dict(
                required=False
            ),
            mode=dict(
                required=False,
                type="str"
            ),
        ),
        supports_check_mode=True,
    )

    p = ContainerEnvironments(module)
    result = p.run()

    module.log(msg="= result: {}".format(result))
    module.exit_json(**result)


if __name__ == '__main__':
    main()
