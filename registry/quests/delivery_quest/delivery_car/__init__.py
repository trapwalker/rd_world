# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

import sublayers_server.model.messages as messages
from sublayers_world.registry.quests.delivery_quest import DeliveryQuest
from sublayers_server.model.registry_me.randomize_examples import RandomizeExamples
from sublayers_server.model.quest_events import OnNote, OnTimer, OnCancel
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import RegistryLinkField, ListField
from sublayers_server.model.registry_me.classes.quests import Cancel, QuestState_, WinState, FailState, FailByCancelState

from functools import partial
import random


class DeliveryCar(DeliveryQuest):
    delivery_car_list = ListField(
        root_default=list,
        caption=u'Список машинок',
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.mobiles.Car'),
    )
    delivery_car = RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.mobiles.Car')

    def as_client_dict(self):
        d = super(DeliveryCar, self).as_client_dict()
        d.update(
            car_uid = self.dc.car_uid,
        )
        return d

    def init_text(self, distance=None):
        self.text_short = u"Доставьте ТС в гороод {}.".format(self.recipient.hometown.title)
        self.text = u"Доставьте ТС: {} - к {} в гороод {}. Награда: {:.0f}nc и {:.0f}ед. опыта.".format(
            self.dc.car_title,
            self.recipient.title,
            self.recipient.hometown.title,
            self.reward_money,
            self.reward_exp,
        )

    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")
        if not self.recipient_list:
            raise Cancel("QUEST CANCEL: Empty recipient_list.")
        if not self.delivery_car_list:
            raise Cancel("QUEST CANCEL: Empty empty delivery_set_list.")

        # Выбираем получателя
        uri = random.choice(self.recipient_list)
        try:
            recipient = event.server.reg.get(uri)
        except:
            raise Cancel("QUEST CANCEL: uri<{}>  not resolve.".format(uri))
        self.recipient = recipient

        # Подготавливаем машинку
        self.delivery_car = random.choice(self.delivery_car_list)
        self.dc.car_title = self.delivery_car.title
        self.dc.car_price = self.delivery_car.price
        self.dc.car_uid = None

        if self.recipient.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.recipient.hometown))
        if self.hirer.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.hirer.hometown))

        distance = self.hirer.hometown.distance_to(self.recipient.hometown)
        distance_cost = self.get_distance_cost(distance=distance)
        self.init_deadline(distance=distance)

        self.total_reward_money = self.total_delivery_money_coef * self.dc.car_price + distance_cost
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста

    def on_start_(self, event, **kw):
        if self.agent.profile.car:
            self.npc_replica(npc=self.hirer, replica=u"Избавься от своей машины.", event=event)
            raise Cancel("QUEST CANCEL: User have car")

        agent_model = self.agent.profile._agent_model
        car_example = RandomizeExamples.get_random_car_level(
            cars=[self.delivery_car],
            weapons=[],
            level=0,
            car_params=dict(
                position=agent_model.current_location.example.position,
                last_location=agent_model.current_location.example,
            )
        )
        self.dc.car_uid = car_example.uid
        agent_model.example.profile.car = car_example
        agent_model.reload_inventory(time=event.time, make_game_log=False)
        messages.UserExampleCarNPCTemplates(agent=agent_model, time=event.time).post()
        messages.UserExampleCarInfo(agent=agent_model, time=event.time).post()
        messages.UserExampleCarView(agent=agent_model, time=event.time).post()
        messages.UserExampleCarSlots(agent=agent_model, time=event.time).post()
        self.log(text=u'Начат квест по доставке ТС.', event=event)

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.delivery_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCDeliveryCarNote,
                time=event.time,
                npc=quest.recipient,
                page_caption=quest.caption,
            )
            quest.set_timer(event=event, name='deadline', delay=quest.deadline)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnTimer) and (event.name == 'deadline'):
                agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                go("fail")

            if isinstance(event, OnNote) and (event.note_uid == quest.dc.delivery_note_uid) and event.result and \
                    agent.car and (agent.car.uid == quest.dc.car_uid):
                agent.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                go('reward')

            if isinstance(event, OnCancel):
                money_penalty = round(quest.reward_money / 2)
                if agent.car and (agent.car.uid == quest.dc.car_uid) and (agent.balance >= money_penalty):
                    agent.set_balance(time=event.time, delta=-money_penalty)
                    agent.car = None
                    agent_model = agent._agent_model
                    agent_model.reload_inventory(time=event.time)
                    messages.UserExampleCarNPCTemplates(agent=agent_model, time=event.time).post()
                    messages.UserExampleCarInfo(agent=agent_model, time=event.time).post()
                    messages.UserExampleCarView(agent=agent_model, time=event.time).post()
                    messages.UserExampleCarSlots(agent=agent_model, time=event.time).post()
                    quest.log(text=u'Уплачен штраф в размере {}nc.'.format(money_penalty), event=event)
                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer, replica=u"Для отказа от квеста верните ТС и заплатите штраф {}nc.".format(money_penalty), event=event)

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            agent_model = agent._agent_model

            agent.car = None
            agent_model.reload_inventory(time=event.time)
            messages.UserExampleCarNPCTemplates(agent=agent_model, time=event.time).post()
            messages.UserExampleCarInfo(agent=agent_model, time=event.time).post()
            messages.UserExampleCarView(agent=agent_model, time=event.time).post()
            messages.UserExampleCarSlots(agent=agent_model, time=event.time).post()

            agent.set_balance(time=event.time, delta=quest.reward_money)
            agent.set_karma(time=event.time, dvalue=quest.reward_karma)
            agent.set_relationship(time=event.time, npc=quest.hirer, dvalue=2)  # todo: relationship сделать правильно
            go('final')

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест провален.', event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест выполнен.', event=event)

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            agent = quest.agent.profile

            # todo: relationship сделать правильно
            agent.set_relationship(time=event.time, npc=quest.recipient, dvalue=-2)  # изменение отношения c нпц
            agent.set_relationship(time=event.time, npc=quest.hirer, dvalue=-2)  # изменение отношения c нпц

            agent.set_karma(time=event.time, dvalue=-quest.reward_karma)
            quest.log(text=u'Квест провален.', event=event)