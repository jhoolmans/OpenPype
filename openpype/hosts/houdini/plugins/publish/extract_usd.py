import os

import pyblish.api
import openpype.api
from openpype.hosts.houdini.api.lib import render_rop


class ExtractUSD(openpype.api.Extractor):

    order = pyblish.api.ExtractorOrder
    label = "Extract USD"
    hosts = ["houdini"]
    families = ["usd",
                "usdModel",
                "usdSetDress"]

    def process(self, instance):

        ropnode = instance[0]

        # Get the filename from the filename parameter
        output = ropnode.evalParm("lopoutput")
        staging_dir = os.path.dirname(output)
        instance.data["stagingDir"] = staging_dir
        file_name = os.path.basename(output)

        self.log.info("Writing USD '%s' to '%s'" % (file_name, staging_dir))

        render_rop(ropnode)

        assert os.path.exists(output), "Output does not exist: %s" % output

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'usd',
            'ext': 'usd',
            'files': file_name,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
