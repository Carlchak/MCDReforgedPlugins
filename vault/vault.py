# -*- coding: utf-8 -*
import os
import time
import uuid
import sqlite3
from decimal import Decimal
from typing import Dict, List, Tuple

from mcdreforged.plugin.server_interface import ServerInterface

PLUGIN_METADATA = {
    'id': 'vault',
    'version': '0.0.1',
    'name': 'Vault',
    'description': 'Vault',
    'author': 'zhang_anzhi',
    'link': 'https://github.com/zhang-anzhi/MCDReforgedPlugins/tree/master/Vault'
}


class AccountNotExistsError(Exception):
    pass


class AmountIllegalError(Exception):
    pass


class InsufficientBalanceError(Exception):
    pass


class Vault:
    AccountNotExistsError = AccountNotExistsError
    AmountIllegalError = AmountIllegalError
    InsufficientBalanceError = InsufficientBalanceError

    def __init__(self, server: ServerInterface):
        self.__server = server
        self.__dir = os.path.join('config', PLUGIN_METADATA['name'])
        if not os.path.exists(self.__dir):
            os.makedirs(self.__dir)
        self.__path = os.path.join(self.__dir, f'{PLUGIN_METADATA["name"]}.db')
        self.__connection = None
        self.__connect()

    # --------
    # Database
    # --------

    def __execute(self, command: str, parameters=(),
                  fetchall=False) -> list or None:
        """Execute a command and commit."""
        cursor = self.__connection.cursor()
        cursor.execute(command, parameters)
        if fetchall:
            return cursor.fetchall()
        cursor.close()
        self.__connection.commit()

    def __connect(self):
        """
        Init database
        1.Connect
        2.Create table if not exist
        3.Tidy database
        """
        # Connect
        self.__connection = sqlite3.connect(self.__path,
                                            check_same_thread=False)

        # Create table
        self.__execute('''
        create table if not exists data(
            name text primary key unique not null,
            time integer not null,
            balance text not null check ( balance>=0 )
        )''')
        self.__execute('''
        create table if not exists log(
            id text primary key unique not null,
            time integer not null,
            debit text not null,
            credit text not null,
            amount text not null
        )''')

        # Tidy
        self.__execute('vacuum')

    def disconnect(self):
        """Disconnect"""
        self.__connection.close()
        self.__connection = None

    # ----
    # Data
    # ----

    def __get_all_data(self) -> dict:
        """Get all data"""
        return {
            name: {'time': t, 'balance': Decimal(balance)}
            for name, t, balance in
            self.__execute('select * from data', fetchall=True)
        }

    def __get_balance(self, name: str) -> Decimal:
        """
        Get account balance.
        :param name: Account name.
        :return: Decimal, balance.
        """
        return self.__get_all_data()[name]['balance']

    def __get_open_time(self, name: str) -> int:
        """
        Get account open time.
        :param name: Account name.
        :return: int, open timestamp.
        """
        return self.__get_all_data()[name]['time']

    def __get_log(self) -> list:
        """Get all log"""
        return self.__execute('select * from log', fetchall=True)

    def __set_balance(self, name: str, balance: Decimal) -> None:
        """
        Set a account's balance.
        :param name: Account name.
        :param balance: New balance.
        :return: None
        """
        self.__execute('update data set balance=? where name=?',
                       (str(balance), name))

    def __log(self, debit: str, credit: str, amount: Decimal) -> None:
        """
        Create a new transfer log.
        :param debit: Debit, the source of capital.
        :param credit: Credit, the went of capital.
        :param amount: Amount of capital.
        :return: None
        """
        self.__execute(f'''
        insert into log values(
            \'{uuid.uuid4()}\',
            {int(time.time())},
            \'{debit}\',
            \'{credit}\',
            \'{str(amount)}\'
        )
        ''')

    # ---
    # API
    # ---

    def create_account(self, name: str) -> None:
        """
        Create new account that balance is 0.0 for a player.
        :param name: The name of player.
        """
        if name not in self.__get_all_data().keys():
            self.__execute(
                f'insert into data values(\'{name}\', {int(time.time())}, \'0.00\')'
            )

    def is_account(self, name) -> bool:
        """
        Check the account is exists.
        :param name: Account name.
        :return: Account is exists or not.
        """
        return name in self.__get_all_data()

    def get_open_time(self, name: str) -> int:
        """
        Get account open time.
        :param name: Account name.
        :return: int, open timestamp.
        :raise AccountNotExistsError when account is not exists.
        """
        if not self.is_account(name):
            raise AccountNotExistsError(f'Account {name} is not exists')
        else:
            return self.__get_open_time(name)

    def get_balance(self, name: str) -> Decimal:
        """
        Get account balance.
        :param name: Account name.
        :return: Decimal, balance.
        :raise AccountNotExistsError when account is not exists.
        """
        if not self.is_account(name):
            raise AccountNotExistsError(f'Account {name} is not exists')
        else:
            return self.__get_balance(name)

    def get_logs(self) -> List[Tuple[str, int, str, str, float]]:
        """
        Get all logs
        :return: A list includes all logs.
        Each log tuple format: (id, time, debit, credit, amount)
        """
        return self.__get_log()

    def get_ranking(self) -> Dict[str, Decimal]:
        """
        Get a amount ranking dict.
        :return: Dict, example: {'a': Decimal('1.5'), 'b': Decimal('1.4')}
        """
        data = {a: b['balance'] for a, b in self.__get_all_data().items()}
        return dict(sorted(data.items(), key=lambda d: d[1], reverse=True))

    def give(self, name: str, amount: Decimal, operator: str = 'Admin') -> None:
        """
        Give a account some money.
        :param name: Account name.
        :param amount: Amount.
        :param operator: The operator will show at 'debit' in logs.
        :return: None
        :raise AccountNotExistsError when account is not exists.
        :raise AmountIllegalError when amount less than or equal to 0.
        """
        # Account exists
        if not self.is_account(name):
            raise AccountNotExistsError(f'Account {name} is not exists')
        # Amount legal
        elif amount <= 0:
            raise AmountIllegalError('Amount can not less than or equal to 0')
        else:
            balance_old = self.__get_balance(name)
            balance_new = balance_old + amount
            self.__set_balance(name, balance_new)
            self.__log(operator, name, amount)

    def take(self, name: str, amount: Decimal, operator: str = 'Admin') -> None:
        """
        Take a account some money.
        :param name: Account name.
        :param amount: Amount.
        :param operator: The operator will show at 'debit' in logs.
        :return: None
        :raise AccountNotExistsError when account is not exists.
        :raise AmountIllegalError when amount less than or equal to 0.
        :raise InsufficientBalanceError when debit's balance is insufficient.
        """
        # Account exists
        if not self.is_account(name):
            raise AccountNotExistsError(f'Account {name} is not exists')
        # Amount legal
        elif amount <= 0:
            raise AmountIllegalError('Amount can not less than or equal to 0')
        # Debit's balance is insufficient
        elif amount > self.__get_balance(name):
            raise InsufficientBalanceError(f"{name}'s balance is insufficient")
        else:
            balance_old = self.__get_balance(name)
            balance_new = balance_old - amount
            self.__set_balance(name, balance_new)
            self.__log(operator, name, -amount)

    def set(self, name: str, amount: Decimal, operator: str = 'Admin') -> None:
        """
        Set a account's balance.
        :param name: Account name.
        :param amount: Amount.
        :param operator: The operator will show at 'debit' in logs.
        :return: None
        :raise AccountNotExistsError when account is not exists.
        :raise AmountIllegalError when amount less than 0.
        """
        # Account exists
        if not self.is_account(name):
            raise AccountNotExistsError(f'Account {name} is not exists')
        # Amount legal
        elif amount < 0:
            raise AmountIllegalError('Amount can not less than 0')
        else:
            balance_old = self.__get_balance(name)
            self.__set_balance(name, amount)
            self.__log(operator, name, amount - balance_old)

    def transfer(self, debit: str, credit: str, amount: Decimal) -> None:
        """
        Transfer amount between two account.
        :param debit: Debit, the source of capital.
        :param credit: Credit, the went of capital.
        :param amount: Amount of capital.
        :return: None
        :raise AccountNotExistsError when account is not exists.
        :raise AmountIllegalError when amount is 0.
        :raise InsufficientBalanceError when debit's balance is insufficient.
        """
        # Account exists
        if not (self.is_account(debit) and self.is_account(credit)):
            info = f'Account {debit} or {credit} are not exists'
            raise AccountNotExistsError(info)
        # Amount legal
        elif amount <= 0:
            raise AmountIllegalError('Amount can not be 0')
        # Debit's balance is insufficient
        elif amount > self.__get_balance(debit):
            raise InsufficientBalanceError(f"{debit}'s balance is insufficient")
        else:
            debit_old = self.get_balance(debit)
            credit_old = self.get_balance(credit)
            debit_new = debit_old - amount
            credit_new = credit_old + amount
            self.__set_balance(debit, debit_new)
            self.__set_balance(credit, credit_new)
            self.__log(debit, credit, amount)


def on_load(server, old):
    global vault
    vault = Vault(server)


def on_unload(server):
    global vault
    vault.disconnect()
