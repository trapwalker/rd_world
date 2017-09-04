# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, RegistryLinkField, ListField, StringField, LocalizedString
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnEnterToLocation
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)

from functools import partial
import random


from sublayers_world.registry.quests.delivery_quest.delivery_quest_simple import DeliveryQuestSimple


class DeliveryPassengerQuest(DeliveryQuestSimple):
    person_delivery_cost = IntField(caption=u'Стоимость достваки одного пассажира', tags={'client'})

    destination_list = ListField(
        root_default=list,
        caption=u"Список пунктов назначения доставки",
        field=RegistryLinkField(),
    )
    destination = RegistryLinkField(
        caption=u'Пункт назначения', document_type='sublayers_server.model.registry_me.classes.poi.Town')

    def init_distance(self):
        town1 = self.hirer.hometown
        town2 = self.destination
        return self.distance_table.get_distance(town1=town1, town2=town2)

    def init_text(self, distance=None):
        self.text_short = LocalizedString(
            en=u"Доставьте пассажиров в гороод {}.".format(self.destination.title),  # TODO: ##LOCALIZATION
            ru=u"Доставьте пассажиров в гороод {}.".format(self.destination.title),
        )
        self.text = LocalizedString(
            en=u"Доставьте пассажиров: {} - в гороод {}. Награда: {:.0f}nc и {:.0f} ед. опыта.".format(  # TODO: ##LOCALIZATION
                ', '.join([unicode(item.title) for item in self.delivery_set]),
                self.destination.title,
                self.reward_money,
                self.reward_exp,
            ),
            ru=u"Доставьте пассажиров: {} - в гороод {}. Награда: {:.0f}nc и {:.0f} ед. опыта.".format(
                ', '.join([unicode(item.title) for item in self.delivery_set]),
                self.destination.title,
                self.reward_money,
                self.reward_exp,
            ),
        )

    def give_passengers(self, event):
        if not self.can_give_items(items=self.delivery_set, event=event):
            return False
        total_inventory_list = (
            None if self.agent.profile._agent_model.inventory is None
            else self.agent.profile._agent_model.inventory.example.total_item_type_info()
        )
        inst_list = []
        for passenger in self.delivery_set:
            inst_list.append(passenger.instantiate())
        self.delivery_set = inst_list
        for passenger in self.delivery_set:
            passenger.init_name()
            self.agent.profile.car.inventory.items.append(passenger)
        if self.agent.profile._agent_model:
            self.agent.profile._agent_model.reload_inventory(time=event.time, save=False, total_inventory=total_inventory_list)
        return True

    def can_take_passengers(self, event):
        if not self.agent.profile.car:
            return False

        if self.agent.profile._agent_model and self.agent.profile._agent_model.inventory:
            self.agent.profile._agent_model.inventory.save_to_example(time=event.time)

        for passenger in self.delivery_set:
            if not self.agent.profile.car.inventory.get_item_by_uid(uid=passenger.uid):
                return False
        return True

    def take_passengers(self, event):
        if not self.can_take_passengers(event=event):
            return False

        inventory_list = self.agent.profile.car.inventory.items[:]
        for passenger in self.delivery_set:
            item = self.agent.profile.car.inventory.get_item_by_uid(uid=passenger.uid)
            inventory_list.remove(item)
        self.agent.profile.car.inventory.items = inventory_list

        if self.agent.profile._agent_model:
            self.agent.profile._agent_model.reload_inventory(time=event.time, save=False)
        return True

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if not self.destination_list:
            raise Cancel("QUEST CANCEL: Empty destination_list.")

        self.init_level()

        # todo: Здесь строки! нужно иметь это ввиду  self.destination = random.choice(self.destination_list)
        d = random.choice(self.destination_list)
        #try:
        #    d = event.server.reg.get(d)
        #except:
        #    raise Cancel("QUEST CANCEL: uri<{}>  not resolve.".format(uri))
        self.destination = d

        self.init_delivery_set()
        cost_delivery_items = len(self.delivery_set) * self.person_delivery_cost

        if self.hirer.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.hirer.hometown))
        distance = self.init_distance()
        self.init_deadline(distance)
        distance_cost = self.get_distance_cost(distance=distance)
        if distance_cost == 0:
            log.wiarning('DeliveryPassenger Quest: Warning!!! Distance from hirer<{}> to recipient<{}> = {}. Change recipient'.format(
                self.hirer, self.recipient, distance))

        self.total_reward_money = self.total_delivery_money_coef * cost_delivery_items + distance_cost
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if self.get_available_lvl() < self.level:
            self.npc_replica(npc=self.hirer, replica=self.locale("q_share_no_rel_npc"), event=event)  ##LOCALIZATION
            raise Cancel("QUEST CANCEL: User have not enough relation")
        if not self.give_passengers(event=event):
            self.npc_replica(npc=self.hirer, replica=self.locale("q_share_no_inv_slot"), event=event)  ##LOCALIZATION
            raise Cancel("QUEST CANCEL: User have not enough empty slot")

        self.log(text=self.locale("q_dp_started"), event=event, position=self.hirer.hometown.position)  ##LOCALIZATION
        temp_log_str = '{} {}.'.format(self.locale("q_dp_in_passengers"), ', '.join([unicode(item.title) for item in self.delivery_set]))
        self.log(text=temp_log_str, event=event, position=self.hirer.hometown.position)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            go('delivery')

    class delivery(QuestState_):
        def on_enter_(self, quest, event):
            quest.set_timer(event=event, name='deadline', delay=quest.deadline)

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnTimer) and (event.name == 'deadline'):
                go("fail")

            if isinstance(event, OnEnterToLocation) and (event.location.example == quest.destination):
                if quest.take_passengers(event=event):
                    temp_log_str = u'{} {}.'.format(
                        quest.locale("q_dp_out_passengers"),
                        ', '.join([unicode(item.title) for item in quest.delivery_set]))
                    quest.log(text=temp_log_str, event=event, position=quest.destination.position)
                    go('reward')

            if isinstance(event, OnCancel):
                if (agent.profile.balance >= (quest.reward_money / 2)) and quest.take_passengers(event=event):
                    agent.profile.set_balance(time=event.time, delta=-(quest.reward_money / 2))
                    temp_log_str = u'{} {}.'.format(
                        quest.locale("q_dp_out_passengers"),  ##LOCALIZATION
                        ', '.join([unicode(item.title) for item in quest.delivery_set]))
                    quest.log(text=temp_log_str, event=event, position=quest.hirer.hometown.position)
                    quest.log(text=u'{} {}nc.'.format(quest.locale("q_share_cancel_pen_done"), quest.reward_money / 2), event=event,  ##LOCALIZATION
                              position=quest.hirer.hometown.position)
                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer, replica=u"{} {}nc.".format(quest.locale("q_share_cancel_pen_done"), quest.reward_money / 2), event=event)

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile
            agent_profile.set_balance(time=event.time, delta=quest.reward_money)
            quest.log(text=u'{} {}nc.'.format(quest.locale("q_dp_reward"), quest.reward_money), event=event,  ##LOCALIZATION
                      position=quest.destination.position)
            agent_profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            agent_profile.set_exp(time=event.time, dvalue=quest.reward_exp)
            agent_profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=quest.reward_relation_hirer)  # изменение отношения к нпц
            if len(quest.reward_items) > 0:
                quest.dc.reward_note_uid = agent_profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.NPCRewardItemsNote,
                    time=event.time,
                    npc=quest.recipient,
                    page_caption=quest.locale("q_share_rewnote_caption"),  ##LOCALIZATION
                    btn1_caption=quest.locale("q_share_rewnote_btn1"),  ##LOCALIZATION
                )
            else:
                go('win')

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    if quest.give_items(items=quest.reward_items, event=event):
                        agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                        go('win')
                    else:
                        quest.npc_replica(npc=quest.hirer, replica=quest.locale("q_share_no_inv_slot"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_share_q_win"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=-quest.level * 2)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-quest.reward_karma)  # todo: изменение кармы
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  ##LOCALIZATION


