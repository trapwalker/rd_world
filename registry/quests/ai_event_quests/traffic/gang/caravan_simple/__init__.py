# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic.gang import AIGangQuest
from sublayers_server.model.registry_me.tree import EmbeddedDocumentField
from sublayers_server.model.registry_me.classes.quests import QuestState_, QuestRange
from sublayers_server.model.registry_me.randomize_examples import RandomizeExamples
from sublayers_server.model.vectors import Point
from sublayers_server.model.quest_events import OnTimer

from ctx_timer import Timer, T
from functools import partial
import random
from math import pi


class AICaravanQuest(AIGangQuest):
    caravan_wait_time = EmbeddedDocumentField(document_type=QuestRange, caption=u"Границы задержки перед стартом каравана (минуты)")

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        return

    def set_actions(self, time):  # Настройка поведенческих квестов
        self.set_main_cc()  # Корректируем скорость группы (вдруг самый медленный сдох)

    def deploy_agents(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        from sublayers_server.model.ai_dispatcher import AIAgent
        from sublayers_server.model.registry_me.classes.agents import Agent as AgentExample

        if not self.routes:
            return

        deplot_timer = Timer()

        with deplot_timer:
            action_quest = event.server.reg.get('/registry/quests/ai_action_quest/traffic')
            route = random.choice(self.routes).instantiate(route_accuracy=200)
            self.dc.route = route
            start_point_route = route.nearest_point(route.get_start_point().as_point())
            level = random.randint(self.bots_level.min, self.bots_level.max)

            for i in range(0, self.dc.count_members):
                example_profile = RandomizeExamples.get_random_agent(level=level, time=event.time, karma_min=self.bots_karma.min, karma_max=self.bots_karma.max)
                example_agent = AgentExample(login='', user_id='', profile=example_profile)
                model_agent = AIAgent(example=example_agent, user=None, time=event.time, server=event.server)
                model_agent.event_quest = self

                car_pos = Point.random_gauss(start_point_route, 30)
                action_quest = action_quest.instantiate(abstract=False, hirer=None, towns_protect=self.towns_protect,
                                                        min_wait_car_time=int(self.dc.start_caravan_deadline * 1.5))  # Чтобы квест не сфейлился сразу
                action_quest.dc.current_target_point = start_point_route
                model_agent.create_ai_quest(time=event.time, action_quest=action_quest)

                car_example = RandomizeExamples.get_random_car_level(
                    level=level,
                    car_params=dict(
                        position=car_pos,
                        direction=random.random() * 2 * pi,
                        base_exp_price=self.bots_car_exp.get_random_int(),
                    )
                )

                example_profile.car = car_example
                self.init_bot_inventory(car_example=car_example)
                self.dc.members.append(model_agent)
        log.debug("Deploy Caravan: {} members =>>> {:.4f}s".format(self.dc.count_members, deplot_timer.duration))

    def deploy_bots(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        for agent in self.dc.members:
            agent.generate_car(time=event.time, car_example=agent.example.profile.car)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        super(AICaravanQuest, self).on_generate_(event=event, **kw)

    ####################################################################################################################
    def on_start_(self, event, **kw):
        super(AICaravanQuest, self).on_start_(event=event, **kw)
        self.dc.start_caravan_deadline = self.caravan_wait_time.get_random_int() * 60
        self.dc.start_caravan_time = event.time + self.dc.start_caravan_deadline
        self.deploy_agents(event=event)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class pre_begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            log.debug('Caravan started in: %ss', quest.dc.start_caravan_deadline)
            quest.set_timer(event=event, name='start_caravan', delay=quest.dc.start_caravan_deadline)

        def on_event_(self, quest, event):
            if isinstance(event, OnTimer) and event.name == 'start_caravan':
                go = partial(quest.go, event=event)
                go('run')

    class run(QuestState_):
        def on_enter_(self, quest, event):
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
            quest.deploy_bots(event=event)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnTimer) and (event.name == 'test_end'):
                status = quest.get_traffic_status(event)
                if status == 'win':
                    quest.displace_bots(event)
                    go('win')
                elif status == 'fail':
                    quest.displace_bots(event)
                    go('fail')
                else:
                    quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
                    quest.set_actions(time=event.time)
                    quest.set_target_point(time=event.time)
    ####################################################################################################################


