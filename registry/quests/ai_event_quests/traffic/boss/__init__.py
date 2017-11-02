# -*- coding: utf-8 -*-

import logging

log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic import AITrafficQuest
from sublayers_server.model.registry_me.tree import IntField
import random


class AIBossQuest(AITrafficQuest):
    action_radius = IntField(caption=u'Максимальная дяльность отклонения от маршрута')

    def set_actions(self, time):  # Настройка поведеньческих квестов
        targets = self.get_visible_targets()
        action_quest = self.dc._main_agent.action_quest
        if not action_quest or not self.dc._main_agent.car or self.dc._main_agent.car.limbo:
            return

        current_target = None
        action_quest.dc.current_cc = 0.5
        if targets:
            action_quest.dc.current_cc = 1.0  # если мы видим когото то ездим активнее
            if self.get_power_ratio(targets=targets, time=time) > 1.0:
                current_target = action_quest.dc.target_car
                current_target_point = action_quest.dc.current_target_point

                # Если текущая цель сдохла или уехала за радиус нашей активности то бросить её
                if (not current_target or
                        (current_target not in targets) or
                        (current_target_point.distance(current_target.position(time=time)) > self.action_radius)):
                    current_target = None

                # Если нет текущей цели то выбрать случайную из тех что в области нашей активноси
                if not current_target:
                    potential_targets = [target for target in targets
                                         if current_target_point.distance(target.position(time=time)) <= self.action_radius]
                    if potential_targets:
                        current_target = random.choice(potential_targets)
            else:
                current_target = None

        action_quest.dc.target_car = current_target

    def is_see_object(self, obj):
        return obj in self.dc._main_agent.get_all_visible_objects()

    class begin(AITrafficQuest.begin):
        def on_enter_(self, quest, event):
            super(AIBossQuest.begin, self).on_enter_(quest=quest, event=event)
            quest.dc.kill_reward_money = 2000
            if event.server.ai_dispatcher:
                event.server.ai_dispatcher.on_event_quest(quest=quest, time=event.time)

