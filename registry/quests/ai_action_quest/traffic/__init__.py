# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.quest_events import OnTimer, OnNote, OnAppendCar, OnDie, OnGetDmg
from sublayers_server.model.registry_me.classes.quests import (
    QuestState_, FailByCancelState, FailState, WinState,
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

    def get_max_cc(self):
        agent_model = self.agent and self.agent.profile._agent_model
        if agent_model:
            return 1.0 if agent_model.target_uid_list else 0.5
        return 1.0

    def discharge_shoot_command(self, event):
        agent_model = self.agent.profile._agent_model
        car = agent_model.car if agent_model else None
        if not car:
            return
        for sector in car.fire_sectors:
            if sector.is_discharge():
                for target_uid in agent_model.target_uid_list:
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

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        pass
    
    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.attacke_target = None
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
                car.set_motion(time=event.time, cc=quest.get_max_cc(), target_point=target_pos)
                quest.set_timer(event=event, name='patrol', delay=5)
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
                    car_pos = car.position(event.time)
                    if quest.route.need_next_point(car_pos):
                        target_pos = quest.route.next_point()
                        if target_pos:
                            car.set_motion(time=event.time, cc=quest.get_max_cc(), target_point=target_pos)
                        else:  # Если нет следующей точки, значит мы закончили маршрут и квест завершён
                            go('win')

                    # Залповая стрельба по всем своим целям
                    quest.discharge_shoot_command(event=event)

                else:
                    log('Car for agent {} not found'.format(agent.login))
                    go('fail')

            if isinstance(event, OnDie):
                go('fail')

            if isinstance(event, OnGetDmg):
                quest.towns_aggro(event=event)

    ####################################################################################################################
    class win(WinState):pass
    ####################################################################################################################
    class fail(FailState):pass
    ####################################################################################################################