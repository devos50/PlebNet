import os
import subprocess
import sys
from argparse import ArgumentParser

from cloudomate.wallet import ElectrumWalletHandler
from cloudomate.cmdline import providers as cloudomate_providers
import cloudomate
from cloudomate.wallet import Wallet

from plebnet import cloudomatecontroller
from plebnet.agent import marketapi
from plebnet.agent.dna import DNA
from plebnet.cloudomatecontroller import options
from plebnet.config import PlebNetConfig

TRIBLER_HOME = "/root/tribler"
PLEBNET_CONFIG = "/root/.plebnet.cfg"
TIME_IN_DAY = 60.0 * 60.0 * 24.0
MAX_DAYS = 5


def execute(cmd=sys.argv[1:]):
    parser = ArgumentParser(description="Plebnet")

    subparsers = parser.add_subparsers(dest="command")
    add_parser_check(subparsers)

    args = parser.parse_args(cmd)
    args.func(args)


def add_parser_check(subparsers):
    parser_list = subparsers.add_parser("check", help="Check plebnet")
    parser_list.set_defaults(func=check)


def check(args):
    """
    Check whether conditions for buying new server are met and proceed if so
    :param args: 
    :return: 
    """
    print("Checking")
    config = PlebNetConfig()

    dna = DNA()
    dna.read_dictionary()

    if not tribler_running():
        print("Tribler not running")
        start_tribler()

    if config.time_since_offer() > TIME_IN_DAY:
        print("Updating daily offer")
        chosen_est_price = update_choice(config, dna)
        place_offer(chosen_est_price)

    if marketapi.get_btc_balance() >= get_cheapest_provider(config)[2]:
        print("Purchase server")
        purchase_choices(config)

    if uninstalled_server_available(config):
        install_server(config)
    config.save()


def tribler_running():
    """
    Check if tribler is running.
    :return: True if twistd.pid exists in /root/tribler
    """
    return os.path.exists(os.path.join(TRIBLER_HOME, '/twistd.pid'))


def start_tribler():
    """
    Start tribler
    :return: 
    """
    return subprocess.call(['twistd', 'plebnet', '-p', '8085', '--exitnode'], cwd=TRIBLER_HOME)


def is_evolve_ready():
    """
    Determine whether the pleb is ready to evolve
    :return: 
    """
    return True


def evolve():
    """
    Execute the commands required to evolve
    :return: 
    """
    # Load DNA
    dna = DNA()
    dna.read_dictionary()

    config = PlebNetConfig()
    config.get('')
    providers = dna.choose()

    # sell mc at transaction cost
    # buy servers
    # wait until both fail/succeed
    # adjust dna evolve based on success
    # create children


def update_choice(config, dna):
    choices = []
    all_providers = dna.dictionary
    excluded_providers = config.get('excluded_providers')
    providers = {k: all_providers[k] for k in all_providers if k in all_providers.keys() - set(excluded_providers)}
    if providers >= 1:
        (provider, option, btc_price) = pick_provider(providers)
        choices.append((provider, option, btc_price))
        del providers[provider]

    if config.time_to_expiration() > MAX_DAYS * TIME_IN_DAY and len(providers) >= 1:
        # if more than 5 days left, pick another, to improve margins
        choices.append(pick_provider(providers))
    config.set('chosen_providers', choices)
    return sum(i[2] for i in choices)


def pick_provider(providers):
    provider = DNA.choose_provider(providers)
    gateway = cloudomate_providers[provider].gateway
    option, price, currency = pick_option(provider)
    btc_price = gateway.estimate_price(
        cloudomate.wallet.get_price(price, currency)) + cloudomate.wallet.get_network_fee()
    return provider, option, btc_price


def pick_option(provider):
    """
    Pick most favorable option at a provider. For now pick most bandwidth per bitcoin
    :param provider: 
    :return: (option, price, currency)
    """
    vpsoptions = options(cloudomate_providers[provider])
    values = []
    for item in vpsoptions:
        bandwidth = item.bandwidth
        if isinstance(bandwidth, str):
            bandwidth = item.connection * 30 * TIME_IN_DAY
        values.append((bandwidth / item.price, item.price, item.currency))
    (bandwidth, price, currency), option = max((v, i) for (i, v) in enumerate(values))
    return option, price, currency


def get_btc_balance():
    # return btc balance of wallet
    pass


def place_offer(chosen_est_price):
    """
    Sell all available MC for the chosen estimated price on the Tribler market.
    :param chosen_est_price: Target amount of BTC to receive
    :return: success of offer placement
    """
    available_mc = marketapi.get_mc_balance()
    if available_mc == 0:
        print("No MC available")
        return False
    return marketapi.put_ask(price=chosen_est_price, price_type='BTC', quantity=available_mc, quantity_type='MC')


def get_cheapest_provider(config):
    """
    Get the price of the cheapest target.
    :param config: config
    :return: price
    """
    providers = config.get('chosen_providers')
    return min(i[2] for i in providers)


def purchase_choices(config):
    """
    Purchase the cheapest provider in chosen_providers. If buying is successful this provider is moved to bought. In any
    case the provider is removed from choices.
    :param config: config
    :return: success
    """
    (provider, vps_option, btc_price) = get_cheapest_provider(config)

    success = cloudomatecontroller.purchase(provider, vps_option, wallet=Wallet())
    if success:
        config.get('bought').append(provider)
    config.get('chosen_providers').remove(provider)
    return success


def uninstalled_server_available(config):
    pass


def install_server(config):
    pass


if __name__ == '__main__':
    execute()
