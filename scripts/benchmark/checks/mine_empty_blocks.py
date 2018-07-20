import logging
import json

from eth.chains.base import (
    MiningChain
)

from .base_benchmark import (
    BaseBenchmark
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

from eth.utils.hexadecimal import (
    encode_hex,
)
from eth.consensus.pow import (
    mine_pow_nonce
)


class MineEmptyBlocksBenchmark(BaseBenchmark):
    POW: dict
    def __init__(self, make_POW_fixtures: bool, num_blocks: int = 500) -> None:
        self.num_blocks = num_blocks
        self.fixture_file = "./scripts/benchmark/fixtures/mine_empty_blocks.json"
        self.make_POW_fixtures = make_POW_fixtures
        self.POW = {}

    @property
    def name(self) -> str:
        return 'Empty block mining'

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        for chain in get_all_chains():

            with open(self.fixture_file, 'r') as outfile:
                self.POW = json.load(outfile)

            value = self.as_timed_result(lambda: self.mine_empty_blocks(chain, self.num_blocks))

            if (self.make_POW_fixtures):
                with open(self.fixture_file, 'w') as outfile:
                    json.dump(self.POW, outfile, indent=4)

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_seconds=value.duration
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)
        return total_stat

    def mine_empty_blocks(self, chain: MiningChain, number_blocks: int) -> None:

        if (self.make_POW_fixtures):
            self.POW[chain.get_vm().fork] = self.update_fixture(chain, number_blocks)
        else :
            vm = chain.get_vm().fork
            for i in range(1, number_blocks + 1):
                nonce = bytes.fromhex(self.POW[vm][str(i)]["nonce"])
                mix_hash = bytes.fromhex(self.POW[vm][str(i)]["mix_hash"])
                block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)
                logging.debug('Block {}'.format(block))


    def update_fixture(self, chain: MiningChain, number_blocks: int) -> dict:
        POW_fork = {}
        for i in range(1, number_blocks + 1):
            POW_block = {}
            block = chain.get_vm().finalize_block(chain.get_block())
            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)

            POW_block["mix_hash"] = mix_hash.hex()
            POW_block["nonce"] = nonce.hex()
            POW_fork[i] = POW_block
            block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)
        return POW_fork
