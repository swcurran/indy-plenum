import json
import types

import pytest
from indy.did import create_and_store_my_did
from indy.ledger import build_nym_request

from plenum.common.constants import NYM, STEWARD, ROLE, VERKEY
from plenum.common.exceptions import UnauthorizedClientRequest, RequestNackedException
from plenum.common.txn_util import get_request_data
from plenum.common.util import randomString
from plenum.server.request_handlers.utils import get_nym_details
from plenum.test.helper import sdk_get_and_check_replies
from plenum.test.pool_transactions.helper import sdk_sign_and_send_prepared_request


@pytest.fixture(scope='module')
def patch_nym_validation(txnPoolNodeSet):
    # Disabling validation for only steward
    def patched_dynamic_validation(self, request):
        self._validate_request_type(request)
        identifier, req_id, operation = get_request_data(request)
        error = None
        if operation.get(ROLE) == STEWARD:
            if self._steward_threshold_exceeded(self.config):
                error = "New stewards cannot be added by other stewards " \
                        "as there are already {} stewards in the system". \
                    format(self.config.stewardThreshold)
        if error:
            raise UnauthorizedClientRequest(identifier,
                                            req_id,
                                            error)

    for n in txnPoolNodeSet:
        n.write_manager.request_handlers[NYM][0].dynamic_validation = types.MethodType(patched_dynamic_validation,
                                                                                       n.write_manager.request_handlers[
                                                                                           NYM][0])


def test_signing_out_of_ledger(looper, txnPoolNodeSet, sdk_wallet_client, sdk_pool_handle, patch_nym_validation):
    seed = randomString(32)
    alias = randomString(5)
    role = None

    wh, _ = sdk_wallet_client
    (sender_did, sender_verkey) = \
        looper.loop.run_until_complete(create_and_store_my_did(wh, json.dumps({'seed': seed})))
    nym_request = looper.loop.run_until_complete(build_nym_request(sender_did, sender_did, sender_verkey, alias, role))

    request_couple = sdk_sign_and_send_prepared_request(looper, (wh, sender_did), sdk_pool_handle, nym_request)
    sdk_get_and_check_replies(looper, [request_couple])

    details = get_nym_details(txnPoolNodeSet[0].states[1], sender_did, is_committed=True)
    assert details[ROLE] == role
    assert details[VERKEY] == sender_verkey


def test_signing_out_of_ledger_empty_verkey(looper, txnPoolNodeSet, sdk_wallet_client, sdk_pool_handle,
                                            patch_nym_validation):
    seed = randomString(32)
    alias = randomString(5)
    role = None

    wh, _ = sdk_wallet_client
    (sender_did, sender_verkey) = \
        looper.loop.run_until_complete(create_and_store_my_did(wh, json.dumps({'seed': seed})))
    nym_request = looper.loop.run_until_complete(build_nym_request(sender_did, sender_did, None, alias, role))

    request_couple = sdk_sign_and_send_prepared_request(looper, (wh, sender_did), sdk_pool_handle, nym_request)

    with pytest.raises(RequestNackedException, match='Can not find verkey for {}'.format(sender_did)):
        sdk_get_and_check_replies(looper, [request_couple])
