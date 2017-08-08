# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import Quest
from sublayers_server.model.registry_me.tree import (IntField, ListField, RegistryLinkField, EmbeddedNodeField,
                                                     FloatField, Subdoc, EmbeddedDocumentField)
from sublayers_server.model.vectors import Point

from math import pi
import random


class LootGenerateRec(Subdoc):
    item = RegistryLinkField(
        document_type='sublayers_server.model.registry_me.classes.item.Item',
        caption=u"Итем который может попасть в инвентарь бота",
    )
    chance = FloatField(default=1.0, caption=u"Вероятность выпадения итема")


class AIEventQuest(Quest):
    delay_time = IntField(root_default=60, caption=u'Минимальное время, между генерациями одного квеста')
    chance_of_generation = FloatField(root_default=1.0, caption=u'Шанс генерации квеста')
    cars = ListField(
        root_default=list,
        caption=u'Список машинок',
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.mobiles.Car'),
    )

    max_loot_count = IntField(root_default=0, caption=u'Максимально возможное количество лута')
    loot_rec_list = ListField(
        root_default=list,
        caption=u"Список для генерации инвентаря бота",
        field=EmbeddedDocumentField(document_type=LootGenerateRec),
        reinst=True
    )

    def init_bot_inventory(self, car_example):
        if not car_example or not self.max_loot_count:
            return
        free_position = max(car_example.inventory.size - len(car_example.inventory.items), 0)
        count_loot = min(random.randint(1, self.max_loot_count), free_position)
        while count_loot:
            item_rec = random.choice(self.loot_rec_list)
            if item_rec.chance >= random.random():
                item = item_rec.item.instantiate()
                car_example.inventory.items.append(item)
            count_loot -= 1

    def can_instantiate(self, event, agent, hirer=None):  # info: попытка сделать can_generate до инстанцирования квеста
        # log.debug('can_generate {} {!r}'.format(self.generation_group, self.parent))
        agent_quests_active = agent.profile.quests_active

        # Этапы проверки:
        # Квест не сгенерируется, если:
        # - парент одинаковый и
        # - достигнуто максимальное количество квестов в данной generation_group и
        # - После сдачи квеста не вышел кулдаун и
        # - После выдачи квеста не прошёл delay_time

        generation_count = 0
        current_time = event.time
        target_parent = self.parent
        target_group = self.generation_group
        for q in agent_quests_active:
            if q.parent == target_parent and q.generation_group == target_group:
                if not q.endtime or q.endtime + q.generation_cooldown > current_time:  # todo: правильно проверять завершённые квестов
                    generation_count += 1
                if q.starttime and q.starttime + q.delay_time > current_time:
                    return False  # Если недавно был выдан хоть один подобный квест, то ждать delay_time обязательно!
        return generation_count < self.generation_max_count and self.chance_of_generation >= random.random()

    def _on_end_quest(self, event):
        super(AIEventQuest, self)._on_end_quest(event=event)
        agent_ended_quests = self.agent and self.agent.profile.quests_ended
        if agent_ended_quests is None:
            return
        # Удалить все квесты, которые совпадают с текущим по q.parent and q.generation_group
        target_parent = self.parent
        target_group = self.generation_group
        quests_ended = []
        for q in agent_ended_quests:
            if q is self or q.parent != target_parent or q.generation_group != target_group:
                quests_ended.append(q)
        self.agent.profile.quests_ended = quests_ended

    @staticmethod
    def can_attack_by_karma(karma_attacker, karma_target):
        if karma_attacker < -1 or karma_attacker > 1:
            karma_attacker = min(max(karma_attacker / 100., -1), 1)
        if karma_target < -1 or karma_target > 1:
            karma_target = min(max(karma_target / 100., -1), 1)

        assert -1 <= karma_attacker <= 1  and -1 <= karma_target <= 1

        if karma_attacker <= -0.75:  # Очень плохие всегда всех атакуют
            return True

        if karma_attacker <= -0.1:  # Просто плохие атакуют по разнице в карме 0.3
            return abs(karma_attacker - karma_target) > 0.3

        if karma_attacker <= 0.1:  # Нейстралы атакуют по разнице в карме, но не трогают Очень хороших
            return karma_target <= 0.75 and abs(karma_attacker - karma_target) > 0.3

        if karma_attacker <= 0.75:  # Хорошие атакуют по разнице в карме плохих и нейтралов. Хорошие не трогают хороших
            return karma_target <= 0.1 and abs(karma_attacker - karma_target) > 0.3

        return False  # Хорошие никого не атакуют

