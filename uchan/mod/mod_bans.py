from flask import render_template, abort, request, flash, redirect, url_for

from uchan import g
from uchan.lib import roles, ArgumentError
from uchan.lib.models import Ban
from uchan.lib.moderator_request import get_authed_moderator
from uchan.lib.utils import now, ip4_to_str
from uchan.mod import mod, mod_role_restrict
from uchan.view import with_token


def get_moderator_or_abort(moderator_id):
    if moderator_id <= 0 or moderator_id > 2 ** 32:
        abort(400)

    moderator = g.moderator_service.find_moderator_id(moderator_id)
    if not moderator:
        abort(404)
    return moderator


@mod.route('/mod_ban')
@mod_role_restrict(roles.ROLE_ADMIN)
def mod_bans():
    bans = g.ban_service.get_all_bans()

    return render_template('mod_bans.html', bans=bans, ip4_to_str=ip4_to_str)


@mod.route('/mod_ban/add', methods=['POST'])
@mod_role_restrict(roles.ROLE_ADMIN)
@with_token()
def mod_ban_add():
    ip4_raw = request.form['ban_ip4']
    if not ip4_raw or len(ip4_raw) > 25:
        abort(400)

    ip4_end_raw = request.form.get('ban_ip4_end', None)
    if not ip4_end_raw:
        ip4_end_raw = None
    if ip4_end_raw is not None and (len(ip4_end_raw) == 0 or len(ip4_end_raw) > 25):
        abort(400)

    ban_length_hours = request.form.get('ban_length', type=int)
    if ban_length_hours is None or ban_length_hours < 0:
        abort(400)

    reason = request.form['ban_reason']

    try:
        ip4 = g.ban_service.parse_ip4(ip4_raw)
        ip4_end = None
        if ip4_end_raw:
            ip4_end = g.ban_service.parse_ip4(ip4_end_raw)
    except ValueError:
        flash('Invalid ip')
        return redirect(url_for('.mod_bans'))

    ban = Ban()
    ban.ip4 = ip4
    if ip4_end is not None:
        ban.ip4_end = ip4_end
    ban.reason = reason
    ban.length = ban_length_hours * 60 * 60 * 1000

    try:
        g.ban_service.add_ban(ban)
        flash('Ban added')
        moderator = get_authed_moderator()
        g.mod_logger.info('{} added ban {} from {} to {} for {} hours reason: {}'.format(
                moderator.username, ban.id, ip4_to_str(ip4), ip4_to_str(ip4_end) if ip4_end is not None else '-', ban_length_hours, reason))
    except ArgumentError as e:
        flash(e.message)

    return redirect(url_for('.mod_bans'))


@mod.route('/mod_ban/delete', methods=['POST'])
@mod_role_restrict(roles.ROLE_ADMIN)
@with_token()
def mod_ban_delete():
    ban_id = request.form.get('ban_id', type=int)
    if not ban_id or ban_id < 0:
        abort(400)

    ban = g.ban_service.find_ban_id(ban_id)
    if not ban:
        abort(404)

    g.ban_service.delete_ban(ban)
    flash('Ban deleted')
    moderator = get_authed_moderator()
    g.mod_logger.info('{} removed ban {}'.format(moderator.username, ban_id))

    return redirect(url_for('.mod_bans'))