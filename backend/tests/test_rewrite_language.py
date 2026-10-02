from test_rewriting import run, StubClient


def test_translated_body_is_rejected():
    def translate(proposal,response,data):
        proposal['edits'][0]['after']='Para correr por carretera, elija un ajuste cómodo. Ningún zapato es el mejor para todos los corredores.'
    result=run(StubClient(translate))
    assert result['status']=='invalid_output'
    assert result['telemetry']['validation_error']['checks_failed']==['language_changed']
    assert 'document' not in result

import pytest
from app.extraction import extract_document
from app.rewriting import rewrite
from app.language_guard import compare_language


@pytest.mark.parametrize('translated',[
    'Pour courir sur la route, choisissez une chaussure confortable. Aucun modèle ne convient parfaitement à tous les coureurs.',
    '道路を走るときは、足に快適にフィットする靴を選んでください。すべてのランナーに最適な靴が一つだけあるわけではありません。',
    'Для бега по дороге выбирайте удобную обувь. Не существует одной модели, которая лучше всего подходит каждому бегуну.',
])
def test_other_language_changes_rejected(translated):
    def translate(proposal,response,data):proposal['edits'][0]['after']=translated
    result=run(StubClient(translate))
    assert result['status']=='invalid_output'
    assert result['telemetry']['validation_error']['checks_failed']==['language_changed']


def test_spanish_source_stays_spanish_despite_english_query_and_metadata():
    document,chunks=extract_document('<main><p>Para correr por carretera, elija un ajuste cómodo. Ningún zapato es el mejor para todos los corredores.</p></main>','html','https://example.com','example.com')
    document['source_metadata']['language']='en'
    def spanish(proposal,response,data):
        proposal['edits'][0]['after']='Elija zapatos cómodos para correr por carretera, porque no existe un modelo que sea el mejor para todos los corredores.'
        assert data['language_policy']['translation_allowed'] is False
        assert data['editable_blocks'][0]['source_language_hint']=='es'
    result=rewrite(document,chunks,['Best running shoes?'],'Preserve original',False,client=StubClient(spanish))
    assert result['status']=='succeeded'


def test_unchanged_language_and_short_text_uncertainty():
    assert run()['status']=='succeeded'
    assert compare_language('CDN','Fast CDN')['status']=='unverified'


def test_technical_english_is_not_misclassified_as_esperanto():
    before='In the world of digital interaction, latency remains one of the most potent influencers of user experience. The difference between 30 ms and 60 ms might seem negligible on paper, but in applications such as multiplayer gaming or live auctions, these milliseconds can tilt the scales significantly. User expectations have soared in tandem with advancements in technology, and a CDN’s ability to ensure low latency is often the measure of its reliability and modernity.'
    after='Latency profoundly impacts user experience in digital applications, from gaming to live auctions. Differences as small as 30 ms can cause user dissatisfaction. Users expect instantaneous content delivery, making CDNs\' ability to maintain consistently low latency a hallmark of their performance and reliability, critical for media streaming, software updates, and SaaS offerings.'
    assert compare_language(before,after)=={'status':'preserved','source_language':'en','proposed_language':'en'}
