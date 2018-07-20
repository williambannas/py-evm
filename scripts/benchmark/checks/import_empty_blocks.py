import logging
import json

from typing import (
    List
)
from eth.chains.base import (
    Chain
)
from eth.consensus.pow import (
    mine_pow_nonce
)
from utils.chain_plumbing import (
    get_all_chains,
)
from utils.format import (
    format_block
)
from utils.reporting import (
    DefaultStat
)
from .base_benchmark import (
    BaseBenchmark
)

class ImportEmptyBlocksBenchmark(BaseBenchmark):
    POW: dict
    def __init__(self, make_POW_fixtures: bool, num_blocks: int = 500) -> None:
        self.num_blocks = num_blocks
        self.make_POW_fixtures = make_POW_fixtures
        self.fixture_file = "./scripts/benchmark/fixtures/import_empty_blocks.json"
        self.POW = {}

    @property
    def name(self) -> str:
        return 'Empty block import'

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        for chain in get_all_chains():

            block = chain.get_vm().finalize_block(chain.get_block())

            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)
            self.block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)

            with open(self.fixture_file, 'r') as outfile:
                self.POW = json.load(outfile)

            val = self.as_timed_result(lambda: self.import_empty_blocks(chain, self.num_blocks))

            if (self.make_POW_fixtures):
                with open(self.fixture_file, 'w') as outfile:
                    json.dump(self.POW, outfile, indent=4)

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_seconds=val.duration
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat

    def import_empty_blocks(self, chain: Chain, number_blocks: int) -> int:

        total_gas_used = 0

        if (self.make_POW_fixtures):
            self.POW[chain.get_vm().fork] = self.update_fixture(chain, number_blocks)
        else:
            vm = chain.get_vm().fork
            for i in range(2, number_blocks + 1):
                nonce = bytes.fromhex(self.POW[vm][str(i)]["nonce"])
                mix_hash = bytes.fromhex(self.POW[vm][str(i)]["mix_hash"])
                state_root = bytes.fromhex(self.POW[vm][str(i)]["state_root"])

                block = chain.get_vm().generate_block_from_parent_header_and_coinbase(self.block.header, self.block.header.coinbase)
                block.header._nonce = nonce
                block.header._mix_hash = mix_hash
                block.header._state_root = state_root

                chain.import_block(block)
                self.block = block

                total_gas_used = total_gas_used + block.header.gas_used
                logging.debug(format_block(block))

        return total_gas_used

    def update_fixture(self, chain: Chain, number_blocks: int) -> dict:
        POW_fork = {}
        for i in range(2, number_blocks + 1):
            POW_block = {}
            block = chain.get_vm().finalize_block(chain.get_block())
            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)

            block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)

            POW_block["mix_hash"] = mix_hash.hex()
            POW_block["nonce"] = nonce.hex()
            POW_block["state_root"] = block.header.state_root.hex()
            POW_fork[i] = POW_block

            self.block = block

        return POW_fork
