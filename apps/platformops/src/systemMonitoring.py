import os
import yaml
from pathlib import Path

def get_infra_service_group_mapping():
    # Load the configuration file
    config_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    with open(os.path.join(config_path, 'cPlatform_config.yaml'), 'r') as fh:
        cplatform_config = yaml.load(fh, Loader=yaml.FullLoader)

    # Get the INFRA_SERVICE_GROUPNAME_MAP section
    infraService_config = cplatform_config.get('INFRA_SERVICE_GROUPNAME_MAP', {})

    return infraService_config
