#! /usr/bin/env nix-shell
#! nix-shell -i bash -p bash jq

jq -r -s -f /dev/stdin <(git show @:versions.json) versions.json <<'EOF'
.[0] as $old |
.[1] as $new |

($old.releases.stable != $new.releases.stable) as $changedStable |
($old.releases.experimental != $new.releases.experimental) as $changedExperimental |

def fmt_change_for($channel):
  "\($channel): \($old.releases."\($channel)") -> \($new.releases."\($channel)")";

if $changedStable or $changedExperimental then
  (if $changedStable then [fmt_change_for("stable")] else [] end)
  + (if $changedExperimental then [fmt_change_for("experimental")] else [] end)
  | join("; ")
else
  "dorpping versions"
end,

($new.versions | keys - ($old.versions | keys)) as $added |
if $added | length > 0 then
  "\nAdded:",
  ($added[] | "- \(.)")
else
  empty
end,

($old.versions | keys - ($new.versions | keys)) as $dropped |
if $dropped | length > 0 then
  "\nDropped:",
  ($dropped[] | "- \(.)")
else
  empty
end
EOF

