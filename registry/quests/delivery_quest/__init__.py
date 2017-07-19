# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import FloatField, RegistryLinkField, ListField, EmbeddedNodeField
from sublayers_server.model.quest_events import OnNote
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, WinState,
)

from functools import partial
import random

from sublayers_server.model.registry_me.classes.quests import Quest


class DeliveryQuest(Quest):
    distance_table = RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.disttable.DistTable')
    recipient_list = ListField(
        root_default=list,
        caption=u"Список возможных получателей доставки",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.poi.Institution'),
    )
    recipient = RegistryLinkField(
        caption=u'Получатель доставки',
        tags={'client'},
        document_type='sublayers_server.model.registry_me.classes.poi.Institution',
    )
    total_delivery_money_coef = FloatField(root_default=0,
        caption=u'Множитель общей стоимости награды за квест от стоимости доставляемого товара')
    delivery_set_list = ListField(
        root_default=list,
        caption=u"Список возможных комплектов для доставки",
        field=ListField(
            caption=u"Список возможных наборов итемов для доставки",
            field=EmbeddedNodeField(
                document_type='sublayers_server.model.registry_me.classes.item.Item',
                caption=u"Необходимый итем",
            ),
        ),
    )
    delivery_set = ListField(
        caption=u"Список итемов для доставки",
        tags={'client'},
        field=EmbeddedNodeField(
            document_type='sublayers_server.model.registry_me.classes.item.Item',
            caption=u"Необходимый итем",
        ),
    )

    def init_text(self, distance=None):
        if distance == 0:
            self.text_short = u"Доставьте груз в соседнее здание."
            self.text = u"Доставьте груз: {} - к {}. Награда: {:.0f}nc.".format(
                ', '.join([item.title for item in self.delivery_set]),
                self.recipient.title,
                self.reward_money
            )
            return
        self.text_short = u"Доставьте груз в гороод {}.".format(self.recipient.hometown.title)
        self.text = u"Доставьте груз: {} - к {} в гороод {}. Награда: {:.0f}nc и {:.0f}ед. опыта.".format(
            ', '.join([item.title for item in self.delivery_set]),
            self.recipient.title,
            self.recipient.hometown.title,
            self.reward_money,
            self.reward_exp,
        )
    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if not self.recipient_list:
            raise Cancel("QUEST CANCEL: Empty recipient_list.")
        if not self.delivery_set_list:
            raise Cancel("QUEST CANCEL: Empty empty delivery_set_list.")

        # log('DeliveryQuest recipient_list len = {}'.format(len(self.recipient_list)))
        self.recipient = random.choice(self.recipient_list)
        self.delivery_set = random.choice(self.delivery_set_list)

        cost_delivery_items = 0
        for item in self.delivery_set:
            cost_delivery_items += item.base_price * item.amount / item.stack_size

        if self.recipient.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.recipient.hometown))
        if self.hirer.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.hirer.hometown))

        distance = self.hirer.hometown.distance_to(self.recipient.hometown)
        distance_cost = round(distance / 100.)  # todo: уточнить стоимость 1px пути

        if distance_cost == 0:
            log.warning('Delivery Quest: Warning!!! Distance from hirer<{!r}> to recipient<{!r}> = {}. Change recipient'.format(
                self.hirer, self.recipient, distance))

        self.total_reward_money = self.total_delivery_money_coef * cost_delivery_items + distance_cost
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text(distance)  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if not self.give_items(items=self.delivery_set, event=event):
            self.npc_replica(npc=self.hirer, replica=u"Не хватает места в инвентаре.", event=event)
            raise Cancel("QUEST CANCEL: User have not enough empty slot")

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)

            quest.dc.delivery_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCDeliveryNote,
                time=event.time,
                npc=quest.recipient,
                page_caption=quest.caption,
            )
            go('delivery')

    class delivery(QuestState_):
        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.delivery_note_uid) and (event.result == True) and quest.take_items(
                        items=quest.delivery_set, event=event):
                    agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                    agent.profile.set_relationship(time=event.time, npc=quest.hirer,
                                                   dvalue=2)  # изменение отношения к нпц
                    go('reward')

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile
            agent_profile.set_balance(time=event.time, delta=quest.reward_money)
            agent_profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            if len(quest.reward_items) > 0:
                quest.dc.reward_note_uid = agent_profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.NPCRewardItemsNote,
                    time=event.time,
                    npc=quest.recipient,
                    page_caption=u'Доставка<br>груза',
                    btn1_caption=u'<br>Забрать',
                )
            else:
                go('final')

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    if quest.give_items(items=quest.reward_items, event=event):
                        agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                        go('final')
                    else:
                        quest.npc_replica(npc=quest.hirer, replica=u"Не хватает места в инвентаре.", event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест выполнен.', event=event)

