import random
import threading
import time

import unittest.mock as mock

from cloudomate.hoster.vps.vps_hoster import VpsOption
from plebnet.address_book import AddressBook
from plebnet.demo.node import Node
import copy
from plebnet.messaging import *
from plebnet.demo.qtable_demo import *
from typing import List, Tuple

def generate_new_node_ab(
    port: int,
    new_node_id: str,
    replicating_node: Node,
    notify_interval,
    contact_restore_timeout,
    inactive_nodes_ping_interval
) -> AddressBook:

    new_pub, new_priv = generate_contact_key_pair()

    new_node_contact = Contact(
        id=new_node_id,
        host='127.0.0.1',
        port=port,
        public_key=new_pub
    )

    new_node_contacts_list = copy.deepcopy(replicating_node.address_book.contacts)
    new_node_contacts_list.append(replicating_node.address_book.self_contact)

    return AddressBook(
        self_contact=new_node_contact,
        private_key=new_priv,
        contacts=new_node_contacts_list,
        receiver_notify_interval=notify_interval,
        contact_restore_timeout=contact_restore_timeout,
        inactive_nodes_ping_interval=inactive_nodes_ping_interval
    )

def generate_new_node_qt(
    parent_qt: QTableDemo,
    replicating_option: dict
) -> QTableDemo:

    new_node_qt = copy.deepcopy(parent_qt)

    new_node_qt.replications += 1

    new_node_state = VPSState(
        replicating_option.provider_name,
        replicating_option.offer_name
    )

    new_node_qt.set_self_state(new_node_state)

    return new_node_qt


def make_node_replicate(
        replicating_node: Node,
        replicating_option: ProviderOffer,
        port: int,
        new_node_id: str,
        notify_interval,
        contact_restore_timeout,
        inactive_nodes_ping_interval
    ) -> Node:

    # Sharing qtable
    replicating_node.qtable.share_qtable(replicating_node.address_book)

    replicating_node.qtable.update_qtable(
        replicating_option.get_offer_id(),
        True,
        replicating_node.mb_tokens
    )
    
    # Generating new node address book and creating distributed contact
    new_node_ab = generate_new_node_ab(
        port=port,
        new_node_id=new_node_id,
        replicating_node=replicating_node,
        notify_interval=notify_interval,
        contact_restore_timeout=contact_restore_timeout,
        inactive_nodes_ping_interval=inactive_nodes_ping_interval
    )
    replicating_node.address_book.create_new_distributed_contact(new_node_ab.self_contact)

    new_node_qt = generate_new_node_qt(
        replicating_node.qtable,
        replicating_option
    )

    consumer = LearningConsumer(new_node_qt)

    new_node_ab.receiver.register_consumer(new_node_qt.messaging_channel, consumer)

    new_node = Node(
        new_node_ab,
        new_node_qt
    )

    replicating_node.btc_balance -= replicating_option.price

    return new_node

def generate_root_node(
    contact_id: str,
    port: int,
    notify_interval: float,
    contact_restore_timeout: int,
    inactive_nodes_ping_interval: int,
) -> Node:

    pub, priv = generate_contact_key_pair()

    root_contact = Contact(
        contact_id,
        "127.0.0.1",
        port,
        pub
    )

    root_ab = AddressBook(
        root_contact,
        priv,
        receiver_notify_interval=notify_interval,
        contact_restore_timeout=contact_restore_timeout,
        inactive_nodes_ping_interval=inactive_nodes_ping_interval
    )

    root_qt = QTableDemo()

    root_qt.init_qtable_and_environment(vps_providers)
    root_qt.init_alpha_and_beta()

    root_qt.set_self_state(VPSState(next(iter(vps_providers)), vps_options[0].name))

    root_node = Node(root_ab, root_qt)

    return root_node


def update_nodes_balance(
    nodes: List[Node]
) -> None:

    for node in nodes:

        node.btc_balance += 1
        node.mb_tokens += 1

def replicate_nodes(
    nodes: List[Node],
    port_counter: int,
    id_counter: int,
    notify_interval,
    contact_restore_timeout,
    inactive_nodes_ping_interval
) -> Tuple[int, int]:

    for node in nodes:

        replicate_option = node.qtable.choose_option(vps_providers)

        if node.btc_balance >= replicate_option.price:

            port_counter += 1
            id_counter += 1

            nodes.append(make_node_replicate(
                replicating_node=node,
                replicating_option=replicate_option,
                port=port_counter,
                new_node_id=str(id_counter),
                notify_interval=notify_interval,
                contact_restore_timeout=contact_restore_timeout,
                inactive_nodes_ping_interval=inactive_nodes_ping_interval
            ))



    return port_counter, id_counter


def print_botnet_state(
    nodes: List[Node]
) -> None:

    print("\n==============================")

    for node in nodes:
        
        node.print_node()


def kill_nodes(
    nodes: List[Node], 
    max_node_age: int
) -> None:

    for node in nodes:

        if node.age > max_node_age:

            node.address_book.kill()
            nodes.remove(node)



def demo(
    notify_interval = 0.01,
    contact_restore_timeout=1,
    inactive_nodes_ping_interval=1,
    tick=1,
    max_node_age=15
) -> None:

    id_counter = 1
    port_counter = 8000

    root = generate_root_node(
        contact_id=str(id_counter),
        port=port_counter,
        notify_interval=notify_interval,
        contact_restore_timeout=contact_restore_timeout,
        inactive_nodes_ping_interval=inactive_nodes_ping_interval
    )

    nodes = [root]

    while True:

        # Update nodes btc balance
        update_nodes_balance(nodes)


        # Killing expired nodes
        kill_nodes(
            nodes,
            max_node_age
        )
       
        # Making nodes replicate
        port_counter, id_counter = replicate_nodes(
            nodes=nodes,
            port_counter=port_counter,
            id_counter=id_counter,
            notify_interval=notify_interval,
            contact_restore_timeout=contact_restore_timeout,
            inactive_nodes_ping_interval=inactive_nodes_ping_interval
        )
        
        # Incrementing node age
        for node in nodes:

            node.age += 1

        print_botnet_state(nodes)

        time.sleep(tick)
    

if __name__ == "__main__":
    demo()
