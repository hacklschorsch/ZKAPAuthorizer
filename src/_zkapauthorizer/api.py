# Copyright 2019 PrivateStorage.io, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__all__ = [
    "MorePassesRequired",
    "LeaseRenewalRequired",
    "ZKAPAuthorizerStorageServer",
    "ZKAPAuthorizerStorageClient",
    "ZKAPAuthorizer",
]

# The identifier for this plugin.  This appears in URLs for resources the
# client plugin exposes, configuration files, etc.
NAME = "privatestorageio-zkapauthz-v2"

from ._storage_client import ZKAPAuthorizerStorageClient
from ._storage_server import LeaseRenewalRequired, ZKAPAuthorizerStorageServer
from .storage_common import MorePassesRequired

# This needs to be imported after the above, since it imports those things from here.
# isort: split
from ._plugin import ZKAPAuthorizer
