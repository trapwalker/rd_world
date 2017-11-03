# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnActivateItem
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, RegistryLinkField, ListField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestSetMapWeapon(ClassTypeQuest):
    count = IntField(caption=u"Количество мин или туррелей, которые нужно установить")

    available_activate_items = ListField(
        caption=u"Список разрешённых айтемов",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.item.MapWeaponItem'),
    )

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_journal_text").generate(
            player_name=self.agent.login, task_text=self.locale("q_cq_set_map_weapon_task_text"))  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.count_done = 0  # кол-во установленных мин или туррелей
        self.log(text=self.locale("q_cq_set_map_weapon_started"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCPageNote,
                time=event.time,
                page_caption=quest.locale("q_cq_set_map_weapon_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_set_map_weapon_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.count <= quest.dc.count_done:
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_set_map_weapon_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnActivateItem):
                item = event.item_example
                for candidate in quest.available_activate_items:
                    if item.is_ancestor(candidate):
                        quest.dc.count_done += 1
                        text = LocalizedString(_id='q_cq_set_map_weapon_add_one').generate(title=quest.locale(item.title))  ##LOCALIZATION
                        quest.log(text=text, event=event)
                        break
                if quest.count <= quest.dc.count_done:
                    quest.log(text=quest.locale("q_cq_set_map_weapon_back_to_teacher"), event=event)  ##LOCALIZATION
                    quest.go(event=event, new_state="back_to_teacher")

    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.go(event=event, new_state="win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_set_map_weapon_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
