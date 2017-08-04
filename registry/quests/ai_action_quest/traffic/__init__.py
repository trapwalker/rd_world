# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.quest_events import OnTimer, OnAIOut, OnAISee, OnAppendCar, OnDie, OnGetDmg
from sublayers_server.model.registry_me.classes.quests import (
    QuestState_, FailState, WinState,
)
from sublayers_server.model.registry_me.tree import (RegistryLinkField, ListField, EmbeddedDocumentField)

from sublayers_world.registry.quests.ai_action_quest import AIActionQuest
from functools import partial


class AIActionTrafficQuest(AIActionQuest):
    route = EmbeddedDocumentField(
        document_type='sublayers_server.model.registry_me.classes.routes.Route',
        caption=u"Маршрут квеста (Устанавливается квестом-событием)",
        reinst=True,
    )

    towns_protect = ListField(
        root_default=list,
        caption=u"Список городов покровителей (Устанавливается квестом-событием)",
        reinst=True,
        field=RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.poi.Town',
        ),
    )

    def discharge_shoot_command(self, event):
        agent_model = self.agent.profile._agent_model
        car = agent_model.car if agent_model else None
        if not car:
            return
        target_uid_list = agent_model.event_quest.dc.target_uid_list
        for sector in car.fire_sectors:
            if sector.is_discharge():
                for target_uid in target_uid_list:
                    target = event.server.objects.get(target_uid, None)
                    if target and sector._test_target_in_sector(target=target, time=event.time):
                        car.fire_discharge(side=sector.side, time=event.time)

    def towns_aggro(self, event):
        agent = getattr(event, 'obj', None) and event.obj.main_agent
        if not agent:
            return
        from sublayers_server.model.map_location import Town
        for town in Town.get_towns():
            if town.example in self.towns_protect:
                town.on_enemy_candidate(agent=agent, damage=True, time=event.time)

    def set_motion(self, car, cc, target_point, event):
        if cc != self.dc.last_cc or target_point != self.dc.last_target_point:
            car.set_motion(time=event.time, cc=cc, target_point=target_point)
            self.dc.last_cc = cc
            self.dc.last_target_point = target_point

    def get_target_point(self, car, event):
        target_car = self.dc.target_car
        if target_car and not target_car.limbo:
            return target_car.position(event.time)
        # взять из роута
        car_pos = car.position(event.time)
        if self.route.need_next_point(car_pos):
            return self.route.next_point()
        else:
            return self.route.nearest_point(car_pos)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        pass
    
    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.target_car = None  # Переопределяется квестом-событием
        self.dc.current_cc = 0.5  # Переопределяется квестом-событием
        self.dc.last_cc = 0.0
        self.dc.last_target_point = None
        if not self.route:
            log('Error!!! AIActionTraffic without route')
    
    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class wait_car(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if agent.profile._agent_model.car:
                go('patrol')
            else:
                quest.set_timer(event=event, name='wait_car', delay=10)
    
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnAppendCar) and agent.profile._agent_model.car:
                go('patrol')
            if isinstance(event, OnTimer) and event.name == 'wait_car':
                if agent.profile._agent_model.car:
                    go('patrol')
                else:
                    go('fail')

    ####################################################################################################################
    class patrol(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            car = agent.profile._agent_model.car
            if car:
                car_pos = car.position(event.time)
                target_pos = quest.route.nearest_point(car_pos)
                if target_pos:
                    quest.set_motion(car=car, cc=quest.dc.current_cc, target_point=target_pos, event=event)
                    quest.set_timer(event=event, name='patrol', delay=5)
                else:
                    go('win')
            else:
                log('Car for agent {} not found'.format(agent.login))
                go('fail')

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnTimer) and event.name == 'patrol':
                car = agent.profile._agent_model.car
                if car:
                    quest.set_timer(event=event, name='patrol', delay=3)
                    # Хил по необходимости
                    if car.hp(time=event.time) < 20:
                        quest.use_heal(time=event.time)

                    target_pos = quest.get_target_point(car=car, event=event)
                    if target_pos:
                        quest.set_motion(car=car, cc=quest.dc.current_cc, target_point=target_pos, event=event)
                    else:
                        go('win')

                    quest.discharge_shoot_command(event=event)

                else:
                    log('Car for agent {} not found'.format(agent.login))
                    go('fail')

            if isinstance(event, OnDie):
                go('fail')

            if isinstance(event, OnGetDmg):
                quest.towns_aggro(event=event)

            if isinstance(event, OnAISee) and agent.profile._agent_model.event_quest:
                agent.profile._agent_model.event_quest.on_see_object(event=event)

    ####################################################################################################################
    class win(WinState):pass
    ####################################################################################################################
    class fail(FailState):pass
    ####################################################################################################################