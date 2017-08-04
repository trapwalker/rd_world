# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic import AITrafficQuest
from sublayers_server.model.registry_me.classes.quests import QuestRange
from sublayers_server.model.registry_me.tree import EmbeddedDocumentField
from sublayers_server.model.vectors import Point

from functools import partial
import random
from math import pi


class AIGangQuest(AITrafficQuest):
    count_members = EmbeddedDocumentField(document_type=QuestRange, caption=u"Количество участников")

    def deploy_bots(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        from sublayers_server.model.ai_dispatcher import AIAgent
        from sublayers_server.model.registry_me.classes.agents import Agent as AgentExample

        if not self.routes or not self.cars:
            return

        action_quest = event.server.reg.get('/registry/quests/ai_action_quest/traffic')
        example_profile_proto = event.server.reg.get('/registry/agents/user/ai_quest')
        route = random.choice(self.routes).instantiate()

        for i in range(0, self.dc.count_members):
            car_proto = random.choice(self.cars).instantiate()

            example_profile = self.instantiate_agent(event, example_profile_proto)
            example_agent = AgentExample(login='', user_id='', profile=example_profile)

            agent = AIAgent(
                example=example_agent,
                user=None, time=event.time, server=event.server
            )
            agent.event_quest = self
            action_quest = action_quest.instantiate(abstract=False, hirer=None, route=route, towns_protect=self.towns_protect)

            agent.create_ai_quest(time=event.time, action_quest=action_quest)
            car_example = car_proto.instantiate(
                position=Point.random_gauss(route.get_start_point().as_point(), 30),
                direction=random.random() * 2 * pi,
            )
            self.init_bot_inventory(car_example=car_example)
            agent.generate_car(time=event.time, car_example=car_example)

            self.dc.members.append(agent)

        # log.debug('Quest {!r} deploy_bots: {!r}'.format(self, self.dc._main_agent))

    def displace_bots(self, event):
        # Метод удаления с карты агентов-ботов. Вызывается на при завершении квеста
        main_agent = getattr(self.dc, '_main_agent', None)
        for agent in self.dc.members:
            agent.displace(time=event.time)
            log.debug('Quest {!r} displace bots: {!r}'.format(self, main_agent))
        self.dc.members = []

    def get_traffic_status(self, event):
        main_agent = getattr(self.dc, '_main_agent', None)
        if main_agent and main_agent.car is None:
            return 'fail'
        if main_agent and main_agent.action_quest and main_agent.action_quest.status == 'end':
            # спросить у квеста, пройден ли он и если да, то вернуть 'win'
            return main_agent.action_quest.result

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        self_karma = self.dc._main_agent.example.profile.karma_norm
        if self_karma > 0.3:  # Не добавляет, если карма хорошая
            return
        obj = getattr(event, 'obj', None)
        if obj is None:
            return
        agent = getattr(obj, 'main_agent', None)
        if not agent:
            return
        if abs(agent.example.profile.karma_norm - self_karma) > 0.3:
            # Добавить во враги
            damager_uid = obj.uid
            if damager_uid not in self.dc.target_uid_list:
                self.dc.target_uid_list.append(damager_uid)

    def get_visible_targets(self):
        r = []
        agent_vo = self.dc._main_agent.get_all_visible_objects()
        for target_uid in self.dc.target_uid_list:
            for vo in agent_vo:
                if target_uid == vo.uid:
                    r.append(vo)
        return r

    def get_power_ratio(self, targets, time):
        team_hp = self.get_total_hp(cars=[self.dc._main_agent.car], time=time)
        enemy_hp = self.get_total_hp(cars=targets, time=time)
        team_dps = self.get_total_dps(cars=[self.dc._main_agent.car])
        enemy_dps = self.get_total_dps(cars=targets)
        if enemy_dps == 0:
            return 10
        if team_dps == 0:
            return 0
        return (team_hp / enemy_dps) / (enemy_hp / team_dps)

    def set_actions(self, time):  # Настройка поведеньческих квестов
        targets = self.get_visible_targets()
        action_quest = self.dc._main_agent.action_quest
        if not action_quest or not self.dc._main_agent.car or self.dc._main_agent.car.limbo:
            return
        # Нет видимых целей, значит ехать по маршруту
        if not targets:
            action_quest.dc.target_car = None
            action_quest.dc.current_cc = 0.5
            return
        # Определение run или attacke
        action_quest.dc.current_cc = 1.0
        if self.get_power_ratio(targets=targets, time=time) > 1.0:
            # todo: Выбрать цель для атаки  (Учесть расстояние, хп цели, свою скорость)
            if not action_quest.dc.target_car or action_quest.dc.target_car not in targets:
                action_quest.dc.target_car = random.choice(targets)
        else:
            # Убегать
            action_quest.dc.target_car = None


####################################################################################################################
    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.count_members = self.count_members.get_random_int()
        self.dc.members = []
        super(AIGangQuest, self).__init__(event=event, **kw)

