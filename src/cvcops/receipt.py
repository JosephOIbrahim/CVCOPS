"""Receipts: one JSON file per frame pair, written last. Mission 2 writes the bodies.

The shape is fixed by docs/contracts/receipt.schema.json (cvcops.receipt.v1), with an example beside it. SYNAPSE's
adapter turns each receipt into an observation (docs/contracts/synapse_observation_mapping.md).
"""


def write_receipt(path, data):
    """Validate data against the schema, write it to a temporary name, then os.replace onto path."""
    raise NotImplementedError("write_receipt is Mission 2's work")


def freshness(receipt_path, expected_cache_key):
    """'fresh' when the receipt exists, says ok and carries expected_cache_key; 'stale' when the key differs or it
    says error; 'missing' when there is no receipt or no flow file beside it."""
    raise NotImplementedError("freshness is Mission 2's work")
