import logging
import json

from typing import (
    NamedTuple,
    Tuple,
)

from eth_typing import (
    Address,
)
from eth.chains.base import (
    MiningChain,
)
from eth.rlp.blocks import (
    BaseBlock,
)

from .base_benchmark import (
    BaseBenchmark,
)
from utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    get_all_chains,
    SECOND_ADDRESS,
)
from utils.address import (
    generate_random_address,
)
from utils.reporting import (
    DefaultStat,
)
from utils.shellart import (
    bold_yellow,
)
from utils.tx import (
    new_transaction,
)
from eth.consensus.pow import (
    mine_pow_nonce
)


class SimpleValueTransferBenchmarkConfig(NamedTuple):
    to_address: Address
    greeter_info: str
    json_fixture: str
    num_blocks: int = 1


TO_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=SECOND_ADDRESS,
    greeter_info='Sending to existing address\n',
    json_fixture='to_existing_address.json'
)


TO_NON_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=None,
    greeter_info='Sending to non-existing address\n',
    json_fixture='to_non_existing_address.json'
)

# TODO: Investigate why 21000 doesn't work
SIMPLE_VALUE_TRANSFER_GAS_COST = 22000
RANDOM_SEED = 12


class SimpleValueTransferBenchmark(BaseBenchmark):
    POW: dict
    def __init__(self, config: SimpleValueTransferBenchmarkConfig, make_POW_fixtures: bool) -> None:
        self.config = config
        self.make_POW_fixtures = make_POW_fixtures
        self.fixture_file = "./scripts/benchmark/fixtures/simple_value_transfers/" + self.config.json_fixture
        self.POW = {}

    @property
    def name(self) -> str:
        return 'Simple value transfer'

    def print_result_header(self) -> None:
        logging.info(bold_yellow(self.config.greeter_info))
        super().print_result_header()

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        num_blocks = self.config.num_blocks

        for chain in get_all_chains():

            with open(self.fixture_file, 'r') as outfile:
                self.POW = json.load(outfile)

            value = self.as_timed_result(lambda: self.mine_blocks(chain, num_blocks))

            if (self.make_POW_fixtures):
                with open(self.fixture_file, 'w') as outfile:
                    json.dump(self.POW, outfile, indent=4)

            total_gas_used, total_num_tx = value.wrapped_value

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=num_blocks,
                total_tx=total_num_tx,
                total_seconds=value.duration,
                total_gas=total_gas_used,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat

    def mine_blocks(self, chain: MiningChain, number_blocks: int) -> Tuple[int, int]:
        total_gas_used = 0
        total_num_tx = 0

        if (self.make_POW_fixtures):
            self.POW[chain.get_vm().fork], total_num_tx, total_gas_used = self.update_fixture(chain, number_blocks)
        else:
            for i in range(1, number_blocks + 1):
                num_tx = chain.get_block().header.gas_limit // SIMPLE_VALUE_TRANSFER_GAS_COST
                block = self.mine_block(chain, i, num_tx)
                total_num_tx = total_num_tx + len(block.transactions)
                total_gas_used = total_gas_used + block.header.gas_used

        return total_gas_used, total_num_tx

    def mine_block(self, chain: MiningChain, block_number: int, num_tx: int) -> BaseBlock:
        vm = chain.get_vm().fork
        for i in range(1, num_tx + 1):
            self.apply_transaction(chain)

        nonce = bytes.fromhex(self.POW[vm][str(block_number)]["nonce"])
        mix_hash = bytes.fromhex(self.POW[vm][str(block_number)]["mix_hash"])

        return chain.mine_block(mix_hash=mix_hash, nonce=nonce)

    def apply_transaction(self, chain: MiningChain) -> None:

        if self.config.to_address is None:
            to_address = generate_random_address(RANDOM_SEED)
        else:
            to_address = self.config.to_address

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=to_address,
            amount=100,
            data=b''
        )

        logging.debug('Applying Transaction {}'.format(tx))

        block, receipt, computation = chain.apply_transaction(tx)

        logging.debug('Block {}'.format(block))
        logging.debug('Receipt {}'.format(receipt))
        logging.debug('Computation {}'.format(computation))

    def update_fixture(self, chain: MiningChain, number_blocks: int) -> dict:
        POW_fork = {}
        total_gas_used = 0
        total_num_tx = 0
        for i in range(1, number_blocks + 1):
            POW_block = {}
            num_tx = chain.get_block().header.gas_limit // SIMPLE_VALUE_TRANSFER_GAS_COST

            for j in range(1, num_tx + 1):
                self.apply_transaction(chain)

            block = chain.get_vm().finalize_block(chain.get_block())

            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)

            POW_block["mix_hash"] = mix_hash.hex()
            POW_block["nonce"] = nonce.hex()
            POW_fork[i] = POW_block
            block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)

            total_num_tx = total_num_tx + len(block.transactions)
            total_gas_used = total_gas_used + block.header.gas_used

        return POW_fork, total_num_tx, total_gas_used
