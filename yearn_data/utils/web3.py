import os
from typing import List, Dict, Literal, Union
import json
import requests
import logging
from web3 import Web3
from web3.contract import Contract
from web3.datastructures import AttributeDict
from web3._utils.events import get_event_data
from web3._utils.filters import construct_event_filter_params
from dotenv import load_dotenv

load_dotenv()

w3 = Web3(Web3.HTTPProvider(os.environ['WEB3_PROVIDER']))
logger = logging.getLogger(__name__)
_cache: Dict = dict()

ABI_ENDPOINT = f"https://api.etherscan.io/api?module=contract&action=getabi&address="


def fetch_abi(address: str) -> List[Dict]:
    abi = _cache.get(address)
    if not abi:
        apiKey = os.environ["ETHERSCAN_TOKEN"]
        url = ABI_ENDPOINT + address + f"&apiKey={apiKey}"
        response = requests.get(url)
        if response.status_code != 200:
            logger.debug(f"Failed to fetch abi from address={address}")
            response.raise_for_status()
        abi = response.json()["result"]
        _cache[address] = abi
    return json.loads(abi)


def get_contract(address: str) -> Contract:
    abi = fetch_abi(address)
    address = Web3.toChecksumAddress(address)
    return w3.eth.contract(address=address, abi=abi)


def call(address: str, fn: str, *fn_args, block: Union[int, str] = "latest"):
    contract = get_contract(address)
    return getattr(contract.caller, fn)(*fn_args, block_identifier=block)


def fetch_events(
    address: str,
    event_name: str,
    from_block: Union[int, Literal["latest"]] = "latest",
    to_block: Union[int, Literal["latest"]] = "latest",
) -> List[AttributeDict]:
    # get event abi
    contract = get_contract(address)
    event = getattr(contract.events, event_name)
    event_abi = event._get_event_abi()
    event_abi_codec = event.web3.codec

    _, event_filter_params = construct_event_filter_params(
        event_abi,
        event_abi_codec,
        contract_address=event.address,
        fromBlock=from_block,
        toBlock=to_block,
    )

    # call node over JSON-RPC API
    logs = event.web3.eth.get_logs(event_filter_params)

    # convert raw binary event data to easily manipulable Python objects
    events = [get_event_data(event_abi_codec, event_abi, entry) for entry in logs]
    return events
